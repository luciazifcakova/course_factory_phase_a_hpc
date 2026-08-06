from pydantic import BaseModel, ConfigDict, Field, model_validator
class RScriptArtifact(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    task_id:str=Field(min_length=1)
    lesson_id:str=Field(min_length=1)
    relative_path:str=Field(min_length=3)
    code:str=Field(min_length=1)
    required_packages:tuple[str,...]=()
    expected_outputs:tuple[str,...]=()
    knowledge_ids:tuple[str,...]=()
    @model_validator(mode='after')
    def validate_path(self):
        if not self.relative_path.endswith('.R'):
            raise ValueError('relative_path must end with .R')
        return self
class RCodeGenerationReport(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    scripts:tuple[RScriptArtifact,...]
    generated_count:int=Field(ge=0)
    failed_task_ids:tuple[str,...]=()
