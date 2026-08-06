from dataclasses import dataclass, asdict
from pathlib import PurePosixPath
import re
@dataclass(frozen=True,slots=True)
class RValidationIssue:
    severity:str
    rule:str
    message:str
    line:int|None=None
@dataclass(frozen=True,slots=True)
class RValidationResult:
    ok:bool
    issues:tuple[RValidationIssue,...]
class RCodeValidator:
    FORBIDDEN={
      'system_call':r'\bsystem\s*\(', 'shell_call':r'\bshell\s*\(',
      'download_file':r'\bdownload\.file\s*\(', 'unlink':r'\bunlink\s*\(',
      'file_remove':r'\bfile\.remove\s*\(', 'setwd':r'\bsetwd\s*\(',
      'install_packages':r'\binstall\.packages\s*\(', 'devtools_install':r'\bdevtools::install_'
    }
    def __init__(self,*,allowed_packages:tuple[str,...]=(),maximum_lines:int=500):
        self.allowed_packages=set(allowed_packages); self.maximum_lines=maximum_lines
    def validate(self,code:str,expected_outputs:tuple[str,...]=()):
        issues=[]; lines=code.splitlines()
        if not code.strip(): issues.append(RValidationIssue('error','empty_script','R script is empty.'))
        if len(lines)>self.maximum_lines: issues.append(RValidationIssue('error','script_too_long',f'Script has {len(lines)} lines.'))
        for rule,pattern in self.FORBIDDEN.items():
            rx=re.compile(pattern)
            for i,line in enumerate(lines,1):
                if rx.search(line): issues.append(RValidationIssue('error',rule,f'Forbidden expression: {line.strip()}',i))
        pkg_rx=re.compile(r'\b(?:library|require)\s*\(\s*[\'\"]?([A-Za-z0-9_.]+)')
        for i,line in enumerate(lines,1):
            m=pkg_rx.search(line)
            if m and self.allowed_packages and m.group(1) not in self.allowed_packages:
                issues.append(RValidationIssue('error','unapproved_package',f'Package {m.group(1)!r} is not approved.',i))
        abs_rx=re.compile(r'[\'\"](?:/|~|[A-Za-z]:[\\/])[^\'\"]*[\'\"]')
        for i,line in enumerate(lines,1):
            if abs_rx.search(line): issues.append(RValidationIssue('error','absolute_path','Absolute path detected.',i))
        for output in expected_outputs:
            path=PurePosixPath(output)
            if path.is_absolute() or '..' in path.parts:
                issues.append(RValidationIssue('error','unsafe_output_path',f'Unsafe output path: {output}'))
            elif output not in code:
                issues.append(RValidationIssue('warning','output_not_referenced',f'Expected output {output!r} is not referenced.'))
        return RValidationResult(not any(i.severity=='error' for i in issues),tuple(issues))
