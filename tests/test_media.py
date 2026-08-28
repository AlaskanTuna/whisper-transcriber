"""Media probing and extraction. Uses ffmpeg-generated fixtures, not real recordings."""

import subprocess
from pathlib import Path

import pytest

from src import media


def _make_video(path: Path, seconds: int = 1) -> Path:
    """Generate a tiny silent-tone video so extraction has something real to chew on."""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-f", "lavfi", "-i", f"color=c=black:s=64x64:d={seconds}",
            "-shortest", "-y", str(path),
        ],
        check=True,
    )
    return path


def _make_silent_video(path: Path, seconds: int = 1) -> Path:
    """Generate a video with no audio track at all."""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c=black:s=64x64:d={seconds}",
            "-y", str(path),
        ],
        check=True,
    )
    return path


needs_ffmpeg = pytest.mark.skipif(
    not media.ffmpeg_available(), reason="ffmpeg/ffprobe not installed"
)


class TestClassification:
    @pytest.mark.parametrize("name", ["a.mp3", "a.WAV", "a.m4a", "a.opus"])
    def test_audio(self, name):
        assert media.is_audio(Path(name))

    @pytest.mark.parametrize("name", ["a.mp4", "a.MKV", "a.mov", "a.webm"])
    def test_video_or_audio(self, name):
        # .webm is configured as audio; the rest are video. Either way it is media.
        assert media.is_media(Path(name))

    def test_video_detection_is_case_insensitive(self):
        assert media.is_video(Path("clip.MP4"))

    def test_unknown_extension(self):
        assert not media.is_media(Path("notes.pdf"))

    def test_no_extension(self):
        assert not media.is_media(Path("recording"))


class TestBuildExtractCommand:
    def test_disables_video_and_sets_bitrate(self):
        cmd = media.build_extract_command(Path("in.mp4"), Path("out.mp3"), "320k")
        assert "-vn" in cmd
        assert cmd[cmd.index("-b:a") + 1] == "320k"
        assert cmd[-1] == "out.mp3"

    def test_reads_no_stdin(self):
        # Without -nostdin, ffmpeg competes with questionary for the terminal.
        assert "-nostdin" in media.build_extract_command(Path("a.mp4"), Path("b.mp3"), "192k")


@needs_ffmpeg
class TestProbe:
    def test_reports_streams_and_duration(self, tmp_path):
        info = media.probe(_make_video(tmp_path / "clip.mp4"))
        assert info.has_audio and info.has_video
        assert info.duration == pytest.approx(1.0, abs=0.3)

    def test_audio_only_file(self, tmp_path):
        target = tmp_path / "tone.mp3"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=440:duration=1", "-y", str(target)],
            check=True,
        )
        info = media.probe(target)
        assert info.has_audio and not info.has_video

    def test_non_media_file_raises(self, tmp_path):
        junk = tmp_path / "notes.txt"
        junk.write_text("not a video")
        with pytest.raises(media.MediaError, match="not a valid media file"):
            media.probe(junk)


@needs_ffmpeg
class TestPrepareAudio:
    def test_audio_passes_straight_through(self, tmp_path):
        source = tmp_path / "already.mp3"
        source.touch()
        prepared = media.prepare_audio(source, tmp_path / "audio")
        assert prepared.path == source
        assert not prepared.extracted

    def test_video_is_extracted_into_the_audio_library(self, tmp_path):
        source = _make_video(tmp_path / "clip.mp4")
        audio_dir = tmp_path / "audio"

        prepared = media.prepare_audio(source, audio_dir)

        assert prepared.extracted
        assert prepared.path == audio_dir / "clip.mp3"
        assert prepared.path.stat().st_size > 0

    def test_second_run_reuses_the_cached_extraction(self, tmp_path):
        source = _make_video(tmp_path / "clip.mp4")
        audio_dir = tmp_path / "audio"

        first = media.prepare_audio(source, audio_dir)
        stamp = first.path.stat().st_mtime_ns
        second = media.prepare_audio(source, audio_dir)

        assert second.path.stat().st_mtime_ns == stamp

    def test_stale_cache_is_regenerated(self, tmp_path):
        source = _make_video(tmp_path / "clip.mp4")
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        stale = audio_dir / "clip.mp3"
        stale.write_text("old")
        import os
        os.utime(stale, (0, 0))

        prepared = media.prepare_audio(source, audio_dir)

        assert prepared.path.read_bytes()[:3] != b"old"

    def test_no_keep_produces_a_temporary_file_that_cleans_up(self, tmp_path):
        source = _make_video(tmp_path / "clip.mp4")

        prepared = media.prepare_audio(source, tmp_path / "audio", keep=False)
        assert prepared.temporary and prepared.path.exists()

        prepared.cleanup()
        assert not prepared.path.exists()

    def test_video_without_audio_is_rejected(self, tmp_path):
        source = _make_silent_video(tmp_path / "silent.mp4")
        with pytest.raises(media.MediaError, match="no audio track"):
            media.prepare_audio(source, tmp_path / "audio")

    def test_missing_file(self, tmp_path):
        with pytest.raises(media.MediaError, match="File not found"):
            media.prepare_audio(tmp_path / "nope.mp4", tmp_path / "audio")

    def test_unsupported_type_names_the_supported_ones(self, tmp_path):
        junk = tmp_path / "notes.pdf"
        junk.touch()
        with pytest.raises(media.MediaError, match="Unsupported file type"):
            media.prepare_audio(junk, tmp_path / "audio")
