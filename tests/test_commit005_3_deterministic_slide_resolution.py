from course_factory import LessonArtifactManifest, ManifestFile, SlideLayoutResolver
from course_factory.slide_models import LessonSlideIntent, SlideLayout


def manifest(figures=(), script=True):
    return LessonArtifactManifest(
        lesson_id="LES-001", title="Lesson",
        script=ManifestFile(relative_path="scripts/LES-001.R",absolute_path="/tmp/LES-001.R",content_type="text/x-r-source",size_bytes=1) if script else None,
        figures=tuple(ManifestFile(relative_path=p,absolute_path=f"/tmp/{p}",content_type="image/png" if p.endswith('.png') else "application/pdf",size_bytes=1) for p in figures),
    )


def intent(kind="example", visual=True):
    return LessonSlideIntent.model_validate({
        "lesson_id":"LES-001","lesson_title":"Lesson","slides":[
            {"slide_id":"LES-001-S01","lesson_id":"LES-001","title":"Overview","purpose":"Introduce the lesson.","kind":"overview","wants_visual":False,"wants_code":False},
            {"slide_id":"LES-001-S02","lesson_id":"LES-001","title":"Main slide","purpose":"Teach the central worked example.","kind":kind,"wants_visual":visual,"wants_code":kind=="code_example"},
        ]})


def test_figure_slide_is_created_by_python():
    plan=SlideLayoutResolver.resolve(intent=intent(),lesson_manifest=manifest(("tasks/x/output/figures/example.png",)))
    assert plan.slides[1].layout is SlideLayout.FIGURE_BULLETS
    assert plan.slides[1].figure_artifacts == ("tasks/x/output/figures/example.png",)


def test_missing_figure_degrades_to_bullets_not_failure():
    plan=SlideLayoutResolver.resolve(intent=intent(),lesson_manifest=manifest(()))
    assert plan.slides[1].layout is SlideLayout.BULLETS
    assert plan.slides[1].figure_artifacts == ()


def test_code_layout_resolves_from_manifest():
    plan=SlideLayoutResolver.resolve(intent=intent("code_example",False),lesson_manifest=manifest(script=True))
    assert plan.slides[1].layout is SlideLayout.CODE
    assert plan.slides[1].use_code is True


def test_png_is_preferred_over_pdf():
    plan=SlideLayoutResolver.resolve(intent=intent(),lesson_manifest=manifest(("tasks/x/output/figures/a.pdf","tasks/x/output/figures/b.png")))
    assert plan.slides[1].figure_artifacts[0].endswith("b.png")
