from course_factory import (
    ArtifactCache,
    ArtifactManager,
    BuildState,
    CacheManager,
    ManagedArtifact,
    ProvenanceManager,
)


def test_artifact_graph_tracks_downstream_dependencies():
    manager = ArtifactManager()

    manager.register(
        ManagedArtifact(
            artifact_id="course_spec",
            artifact_type="specification",
            created_by="input_builder",
            payload={"topic": "R"},
        )
    )
    manager.register(
        ManagedArtifact(
            artifact_id="course_outline",
            artifact_type="outline",
            created_by="planner",
            dependencies=("course_spec",),
            payload={"modules": []},
        )
    )
    manager.register(
        ManagedArtifact(
            artifact_id="slide_deck",
            artifact_type="slides",
            created_by="slide_agent",
            dependencies=("course_outline",),
            payload={"slides": []},
        )
    )
    manager.register(
        ManagedArtifact(
            artifact_id="presentation",
            artifact_type="pptx",
            created_by="powerpoint_builder",
            dependencies=("slide_deck",),
            payload={"path": "course.pptx"},
        )
    )

    assert manager.downstream("course_spec") == (
        "course_outline",
        "presentation",
        "slide_deck",
    )


def test_invalidate_downstream_removes_only_dependents():
    manager = ArtifactManager()
    manager.register(
        ManagedArtifact(
            artifact_id="a",
            artifact_type="source",
            created_by="agent",
            payload={"x": 1},
        )
    )
    manager.register(
        ManagedArtifact(
            artifact_id="b",
            artifact_type="derived",
            created_by="agent",
            dependencies=("a",),
            payload={"x": 2},
        )
    )
    manager.register(
        ManagedArtifact(
            artifact_id="c",
            artifact_type="independent",
            created_by="agent",
            payload={"x": 3},
        )
    )

    invalidated = manager.invalidate_downstream("a")

    assert invalidated == ("b",)
    assert manager.exists("a")
    assert not manager.exists("b")
    assert manager.exists("c")


def test_cache_manager_skips_unchanged_artifact(tmp_path):
    cache = CacheManager(ArtifactCache(tmp_path / "cache"))
    checksum = "abc123"

    assert cache.should_execute("slides", checksum) is True

    cache.update(
        "slides",
        checksum=checksum,
        payload={"slides": [1]},
    )

    assert cache.should_execute("slides", checksum) is False
    assert cache.restore("slides") == {"slides": [1]}


def test_provenance_manager_records_build_details(tmp_path):
    artifact = ManagedArtifact(
        artifact_id="slide_deck",
        artifact_type="slides",
        created_by="slide_agent",
        dependencies=("course_outline", "knowledge"),
        payload={"slides": [{"title": "Vectors"}]},
    )

    manager = ProvenanceManager(tmp_path / "provenance")
    record = manager.register(
        artifact=artifact,
        agent_name="slide_agent",
        agent_version="1.0.0",
        llm_model="qwen",
        prompt={"system": "Generate slides"},
        inputs=[{"outline": 1}, {"knowledge": 2}],
        output=artifact.payload,
    )

    assert record.artifact_id == "slide_deck"
    assert record.parent_artifacts == (
        "course_outline",
        "knowledge",
    )
    assert (tmp_path / "provenance" / "slide_deck.json").exists()


def test_build_state_creates_cache_and_provenance_dirs(tmp_path):
    state = BuildState.create(tmp_path)

    assert (tmp_path / ".cache").is_dir()
    assert (tmp_path / "provenance").is_dir()
    assert state.artifacts.all() == ()
