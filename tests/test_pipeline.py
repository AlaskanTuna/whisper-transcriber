"""End-to-end pipeline behaviour, with Whisper and Gemini mocked."""

import pytest

from src import pipeline
from src.llm import LLMError


@pytest.fixture
def fake_whisper(monkeypatch, segments):
    """Replace the Whisper call with a fixed result."""
    import src.transcriber as transcriber

    calls = []

    def fake_transcribe(model, audio_path, language, task):
        calls.append({"path": audio_path, "language": language, "task": task})
        return {"segments": segments, "language": language or "en"}

    monkeypatch.setattr(transcriber, "transcribe", fake_transcribe)
    monkeypatch.setattr(transcriber, "load_model", lambda size: f"model:{size}")
    monkeypatch.setattr(transcriber, "get_device", lambda: "CPU")
    return calls


@pytest.fixture
def audio_file(tmp_path):
    """A real MP3 so probing and passthrough behave normally."""
    import subprocess

    target = tmp_path / "recording.mp3"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1", "-y", str(target)],
        check=True,
    )
    return target


class TestJobOptions:
    def test_polish_is_driven_by_the_format_list(self):
        assert pipeline.JobOptions(formats=["txt", "md"]).polish
        assert not pipeline.JobOptions(formats=["txt"]).polish


class TestRunJob:
    def test_writes_requested_formats_beside_the_input(self, audio_file, fake_whisper):
        opts = pipeline.JobOptions(formats=["txt", "srt"], audio_dir=audio_file.parent / "lib")
        result = pipeline.run_job(audio_file, "model", opts)

        assert result.success
        assert {p.name for p in result.outputs} == {"recording.txt", "recording.srt"}
        assert (audio_file.parent / "recording.txt").exists()

    def test_explicit_output_directory_is_honoured(self, audio_file, fake_whisper, tmp_path):
        dest = tmp_path / "notes"
        opts = pipeline.JobOptions(
            formats=["txt"], output=dest, audio_dir=tmp_path / "lib"
        )
        result = pipeline.run_job(audio_file, "model", opts)

        assert result.outputs == [dest / "recording.txt"]

    def test_existing_output_is_skipped_without_overwrite(self, audio_file, fake_whisper):
        existing = audio_file.parent / "recording.txt"
        existing.write_text("keep me")
        opts = pipeline.JobOptions(formats=["txt"], audio_dir=audio_file.parent / "lib")

        result = pipeline.run_job(audio_file, "model", opts)

        assert result.skipped == [existing]
        assert existing.read_text() == "keep me"

    def test_all_outputs_present_skips_whisper_entirely(self, audio_file, fake_whisper):
        # Whisper costs minutes; re-running a finished job must not pay that
        # only to throw every result away.
        for name in ("recording.txt", "recording.srt"):
            (audio_file.parent / name).write_text("done")
        opts = pipeline.JobOptions(
            formats=["txt", "srt"], audio_dir=audio_file.parent / "lib"
        )

        result = pipeline.run_job(audio_file, "model", opts)

        assert result.success
        assert len(result.skipped) == 2
        assert fake_whisper == []

    def test_partial_outputs_still_run(self, audio_file, fake_whisper):
        (audio_file.parent / "recording.txt").write_text("done")
        opts = pipeline.JobOptions(
            formats=["txt", "srt"], audio_dir=audio_file.parent / "lib"
        )

        result = pipeline.run_job(audio_file, "model", opts)

        assert len(fake_whisper) == 1
        assert [p.name for p in result.outputs] == ["recording.srt"]

    def test_overwrite_replaces_it(self, audio_file, fake_whisper):
        existing = audio_file.parent / "recording.txt"
        existing.write_text("keep me")
        opts = pipeline.JobOptions(
            formats=["txt"], overwrite=True, audio_dir=audio_file.parent / "lib"
        )

        pipeline.run_job(audio_file, "model", opts)

        assert existing.read_text() != "keep me"

    def test_missing_source_fails_cleanly(self, tmp_path, fake_whisper):
        opts = pipeline.JobOptions(formats=["txt"])
        result = pipeline.run_job(tmp_path / "gone.mp3", "model", opts)

        assert not result.success
        assert "File not found" in result.error

    def test_video_input_is_extracted_then_transcribed(self, tmp_path, fake_whisper):
        import subprocess

        source = tmp_path / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
             "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
             "-shortest", "-y", str(source)],
            check=True,
        )
        library = tmp_path / "lib"
        opts = pipeline.JobOptions(formats=["txt"], audio_dir=library)

        result = pipeline.run_job(source, "model", opts)

        assert result.success
        assert result.extracted_audio == library / "clip.mp3"
        # Whisper saw the extracted audio, but output is named for the video.
        assert fake_whisper[0]["path"] == library / "clip.mp3"
        assert (tmp_path / "clip.txt").exists()

    def test_polish_writes_markdown_and_keeps_the_transcript(
        self, audio_file, fake_whisper, monkeypatch
    ):
        import src.polish as polish_module

        monkeypatch.setattr(
            polish_module, "polish",
            lambda segments, meta, profile, context, on_progress: polish_module.PolishResult(
                markdown="# Document\n", errors=[]
            ),
        )
        opts = pipeline.JobOptions(formats=["txt", "md"], audio_dir=audio_file.parent / "lib")

        result = pipeline.run_job(audio_file, "model", opts)

        assert (audio_file.parent / "recording.md").read_text() == "# Document\n"
        assert (audio_file.parent / "recording.txt").exists()
        assert result.warnings == []

    def test_polish_failure_is_a_warning_not_a_failure(
        self, audio_file, fake_whisper, monkeypatch
    ):
        import src.polish as polish_module

        def boom(*a, **k):
            raise LLMError("no quota")

        monkeypatch.setattr(polish_module, "polish", boom)
        opts = pipeline.JobOptions(formats=["txt", "md"], audio_dir=audio_file.parent / "lib")

        result = pipeline.run_job(audio_file, "model", opts)

        assert result.success
        assert (audio_file.parent / "recording.txt").exists()
        assert any("no quota" in w for w in result.warnings)

    def test_progress_reports_a_stage_for_each_step(self, audio_file, fake_whisper):
        # Front-ends key off the stage name to hand the terminal to Whisper's
        # own progress bar, so the stage must be reported, not just a message.
        seen = []
        opts = pipeline.JobOptions(formats=["txt"], audio_dir=audio_file.parent / "lib")

        pipeline.run_job(audio_file, "model", opts, on_progress=lambda stage, msg: seen.append(stage))

        assert "transcribe" in [stage for stage in seen]

    def test_video_input_reports_an_extract_stage(self, tmp_path, fake_whisper):
        import subprocess

        source = tmp_path / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
             "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
             "-shortest", "-y", str(source)],
            check=True,
        )
        seen = []
        opts = pipeline.JobOptions(formats=["txt"], audio_dir=tmp_path / "lib")

        pipeline.run_job(source, "model", opts, on_progress=lambda stage, msg: seen.append(stage))

        assert seen[0] == "extract"

    def test_language_and_task_reach_whisper(self, audio_file, fake_whisper):
        opts = pipeline.JobOptions(
            formats=["txt"], language="en", task="translate",
            audio_dir=audio_file.parent / "lib",
        )
        pipeline.run_job(audio_file, "model", opts)

        assert fake_whisper[0]["language"] == "en"
        assert fake_whisper[0]["task"] == "translate"


class TestRunJobs:
    def test_loads_the_model_once_for_many_files(self, tmp_path, fake_whisper, monkeypatch):
        import subprocess

        loaded = []
        import src.transcriber as transcriber
        monkeypatch.setattr(
            transcriber, "load_model", lambda size: loaded.append(size) or "model"
        )

        sources = []
        for name in ("a.mp3", "b.mp3"):
            target = tmp_path / name
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                 "-i", "sine=frequency=440:duration=1", "-y", str(target)],
                check=True,
            )
            sources.append(target)

        results = pipeline.run_jobs(
            sources, pipeline.JobOptions(formats=["txt"], audio_dir=tmp_path / "lib")
        )

        assert len(loaded) == 1
        assert all(r.success for r in results)

    def test_no_sources_does_nothing(self):
        assert pipeline.run_jobs([], pipeline.JobOptions()) == []
