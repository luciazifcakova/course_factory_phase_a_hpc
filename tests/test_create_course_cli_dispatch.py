from course_factory import __main__ as cli


def test_create_course_dispatch_is_present(monkeypatch):
    called = {}

    monkeypatch.setattr(
        cli,
        "command_create_course",
        lambda args: called.setdefault("create-course", 0),
    )
    monkeypatch.setattr(
        cli,
        "initialize_workspace",
        lambda: None,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "course-factory",
            "create-course",
            "--prompt",
            "Create an introduction to ggplot2 course",
        ],
    )

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 0

    assert called == {"create-course": 0}
