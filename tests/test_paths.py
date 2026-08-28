"""The output-location rules -- the thing that removes the copy-out step."""

from src import paths


class TestPlanOutput:
    def test_file_outside_the_project_writes_beside_itself(self, tmp_path):
        source = tmp_path / "videos" / "standup.mp4"
        source.parent.mkdir()
        source.touch()

        plan = paths.plan_output(source, None, tmp_path / "audio", tmp_path / "transcripts")

        assert plan.directory == source.parent
        assert plan.stem == "standup"
        assert plan.path_for("md") == source.parent / "standup.md"

    def test_file_in_the_audio_library_writes_to_transcripts(self, tmp_path):
        audio_dir = tmp_path / "audio"
        output_dir = tmp_path / "transcripts"
        audio_dir.mkdir()
        source = audio_dir / "call.mp3"
        source.touch()

        plan = paths.plan_output(source, None, audio_dir, output_dir)

        assert plan.directory == output_dir
        assert plan.stem == "call"

    def test_explicit_directory_wins(self, tmp_path):
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        source = audio_dir / "call.mp3"
        source.touch()
        elsewhere = tmp_path / "notes"
        elsewhere.mkdir()

        plan = paths.plan_output(source, elsewhere, audio_dir, tmp_path / "transcripts")

        assert plan.directory == elsewhere
        assert plan.stem == "call"

    def test_explicit_file_path_sets_both_directory_and_stem(self, tmp_path):
        source = tmp_path / "call.mp3"
        source.touch()

        plan = paths.plan_output(source, tmp_path / "out" / "renamed.md")

        assert plan.directory == tmp_path / "out"
        assert plan.stem == "renamed"

    def test_nonexistent_suffixless_output_is_treated_as_a_directory(self, tmp_path):
        source = tmp_path / "call.mp3"
        source.touch()

        plan = paths.plan_output(source, tmp_path / "not_yet_created")

        assert plan.directory == tmp_path / "not_yet_created"
        assert plan.stem == "call"

    def test_dotted_source_name_keeps_its_full_stem(self, tmp_path):
        source = tmp_path / "2026-08-28 14-34-12.mp4"
        source.touch()

        plan = paths.plan_output(source, None)

        assert plan.stem == "2026-08-28 14-34-12"


class TestIsInside:
    def test_direct_child(self, tmp_path):
        child = tmp_path / "a.mp3"
        child.touch()
        assert paths.is_inside(child, tmp_path)

    def test_sibling_is_not_inside(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        assert not paths.is_inside(b / "x.mp3", a)


class TestCollectMedia:
    def test_expands_a_directory_and_drops_non_media(self, tmp_path):
        (tmp_path / "one.mp3").touch()
        (tmp_path / "two.mp4").touch()
        (tmp_path / "notes.txt").touch()

        found = paths.collect_media([tmp_path])

        assert {f.name for f in found} == {"one.mp3", "two.mp4"}

    def test_deduplicates_across_arguments(self, tmp_path):
        f = tmp_path / "one.mp3"
        f.touch()

        found = paths.collect_media([f, tmp_path, f])

        assert len(found) == 1

    def test_explicit_files_are_kept_even_with_odd_extensions(self, tmp_path):
        # Naming a file directly is an instruction, not a guess; the pipeline
        # reports the unsupported type with a clear message.
        f = tmp_path / "recording.aiff"
        f.touch()
        assert paths.collect_media([f]) == [f]

    def test_missing_paths_are_ignored(self, tmp_path):
        assert paths.collect_media([tmp_path / "nope.mp3"]) == []
