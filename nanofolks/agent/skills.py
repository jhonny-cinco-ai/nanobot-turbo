"""Skills loader for agent capabilities."""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from loguru import logger

# Default builtin skills directory (relative to this file)
BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillVerificationStatus:
    """Security verification status for a skill."""
    PENDING = "pending"      # Not yet scanned
    APPROVED = "approved"    # Passed security scan
    REJECTED = "rejected"    # Failed security scan (dangerous)
    MANUAL_APPROVAL = "manual_approval"  # Flagged but user approved


class SkillsLoader:
    """
    Loader for agent skills with security verification.
    
    Skills are markdown files (SKILL.md) that teach the agent how to use
    specific tools or perform certain tasks.
    
    Security Features:
    - Automatic security scanning on skill discovery
    - Approval workflow for skills with security warnings
    - Prevents unverified skills from being loaded
    - Shows verification status in skill listings
    """
    
    def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR
        self.verification_dir = workspace / ".nanofolks" / "skill-verification"
        self.verification_dir.mkdir(parents=True, exist_ok=True)
        
        # Auto-scan any new skills on initialization
        self._auto_scan_new_skills()
    
    def _auto_scan_new_skills(self) -> None:
        """Automatically scan any unverified workspace skills."""
        if not self.workspace_skills.exists():
            return
        
        for skill_dir in self.workspace_skills.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                status = self.get_verification_status(skill_dir.name)
                if status == SkillVerificationStatus.PENDING:
                    logger.info(f"New skill detected: {skill_dir.name}, running security scan...")
                    self._scan_skill_for_verification(skill_dir.name)
    
    def get_verification_status(self, skill_name: str) -> str:
        """
        Get verification status for a skill.
        
        Built-in skills are always approved. Workspace skills require scanning.
        """
        # Check if built-in (always approved)
        if self.builtin_skills and (self.builtin_skills / skill_name / "SKILL.md").exists():
            return SkillVerificationStatus.APPROVED
        
        # Check workspace
        verification_file = self.verification_dir / f"{skill_name}.json"
        if verification_file.exists():
            try:
                import json
                data = json.loads(verification_file.read_text())
                return data.get("status", SkillVerificationStatus.PENDING)
            except:
                pass
        
        # No verification record - pending
        return SkillVerificationStatus.PENDING
    
    def _scan_skill_for_verification(self, skill_name: str) -> dict:
        """Run security scan and save results."""
        try:
            from nanofolks.security.skill_scanner import scan_skill
            
            skill_path = self.workspace_skills / skill_name
            report = scan_skill(skill_path)
            
            # Determine status
            if report.passed:
                status = SkillVerificationStatus.APPROVED
            else:
                status = SkillVerificationStatus.REJECTED
            
            # Save verification record
            import json
            verification_file = self.verification_dir / f"{skill_name}.json"
            verification_data = {
                "status": status,
                "risk_score": report.total_risk_score,
                "critical_count": report.critical_count,
                "high_count": report.high_count,
                "scanned_at": str(Path.home()),  # Simple timestamp placeholder
                "passed": report.passed,
                "findings_count": len(report.findings)
            }
            verification_file.write_text(json.dumps(verification_data, indent=2))
            
            logger.info(f"Skill {skill_name} verification: {status} (risk: {report.total_risk_score}/100)")
            return verification_data
            
        except Exception as e:
            logger.error(f"Failed to scan skill {skill_name}: {e}")
            return {"status": SkillVerificationStatus.PENDING, "error": str(e)}
    
    def approve_skill(self, skill_name: str) -> bool:
        """
        Manually approve a skill (overrides security warnings).
        
        Returns:
            True if approved successfully
        """
        verification_file = self.verification_dir / f"{skill_name}.json"
        
        try:
            import json
            if verification_file.exists():
                data = json.loads(verification_file.read_text())
            else:
                data = {}
            
            data["status"] = SkillVerificationStatus.MANUAL_APPROVAL
            data["approved_manually"] = True
            data["approved_at"] = str(Path.home())  # Placeholder
            
            verification_file.write_text(json.dumps(data, indent=2))
            logger.info(f"Skill {skill_name} manually approved")
            return True
        except Exception as e:
            logger.error(f"Failed to approve skill {skill_name}: {e}")
            return False
    
    def reject_skill(self, skill_name: str) -> bool:
        """Mark a skill as rejected/dangerous."""
        verification_file = self.verification_dir / f"{skill_name}.json"
        
        try:
            import json
            if verification_file.exists():
                data = json.loads(verification_file.read_text())
            else:
                data = {}
            
            data["status"] = SkillVerificationStatus.REJECTED
            data["rejected_at"] = str(Path.home())
            
            verification_file.write_text(json.dumps(data, indent=2))
            logger.info(f"Skill {skill_name} rejected")
            return True
        except Exception as e:
            logger.error(f"Failed to reject skill {skill_name}: {e}")
            return False
    
    def list_skills(self, filter_unavailable: bool = True, include_verification: bool = True) -> list[dict]:
        """
        List all available skills.
        
        Args:
            filter_unavailable: If True, filter out skills with unmet requirements.
            include_verification: If True, include verification status in skill info.
        
        Returns:
            List of skill info dicts with 'name', 'path', 'source', 'verified'.
        """
        skills = []
        
        # Workspace skills (highest priority)
        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        skill_info = {
                            "name": skill_dir.name, 
                            "path": str(skill_file), 
                            "source": "workspace",
                        }
                        if include_verification:
                            skill_info["verified"] = self.get_verification_status(skill_dir.name)
                            # Get risk score if available
                            verification_file = self.verification_dir / f"{skill_dir.name}.json"
                            if verification_file.exists():
                                try:
                                    import json
                                    vdata = json.loads(verification_file.read_text())
                                    skill_info["risk_score"] = str(vdata.get("risk_score", 0))
                                except:
                                    skill_info["risk_score"] = "0"
                        skills.append(skill_info)
        
        # Built-in skills (always verified)
        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists() and not any(s["name"] == skill_dir.name for s in skills):
                        skill_info = {
                            "name": skill_dir.name, 
                            "path": str(skill_file), 
                            "source": "builtin",
                        }
                        if include_verification:
                            skill_info["verified"] = SkillVerificationStatus.APPROVED
                            skill_info["risk_score"] = "0"
                        skills.append(skill_info)
        
        # Filter by requirements and verification (unless showing all)
        if filter_unavailable:
            filtered = []
            for s in skills:
                # Check requirements
                if not self._check_requirements(self._get_skill_meta(s["name"])):
                    continue
                # Check verification - only allow approved or manually approved
                if include_verification:
                    verified = s.get("verified", SkillVerificationStatus.PENDING)
                    if verified not in [SkillVerificationStatus.APPROVED, SkillVerificationStatus.MANUAL_APPROVAL]:
                        continue
                filtered.append(s)
            return filtered
        return skills
    
    def load_skill(self, name: str) -> str | None:
        """
        Load a skill by name.
        
        Args:
            name: Skill name (directory name).
        
        Returns:
            Skill content or None if not found.
        """
        # Check workspace first
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return workspace_skill.read_text(encoding="utf-8")
        
        # Check built-in
        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return builtin_skill.read_text(encoding="utf-8")
        
        return None
    
    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """
        Load specific skills for inclusion in agent context.
        
        Args:
            skill_names: List of skill names to load.
        
        Returns:
            Formatted skills content.
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                parts.append(f"### Skill: {name}\n\n{content}")
        
        return "\n\n---\n\n".join(parts) if parts else ""
    
    def build_skills_summary(self, show_all: bool = True) -> str:
        """
        Build a summary of all skills (name, description, path, availability).
        
        This is used for progressive loading - the agent can read the full
        skill content using read_file when needed.
        
        Args:
            show_all: If True, includes pending/rejected skills that need approval.
        
        Returns:
            XML-formatted skills summary.
        """
        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Get approved skills (available for use)
        approved_skills = self.list_skills(filter_unavailable=False, include_verification=True)
        
        # Get all skills including pending if show_all is True
        all_skills = approved_skills
        pending_skills = []
        rejected_skills = []
        
        if show_all and self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    # Check if already in approved list
                    if not any(s["name"] == skill_dir.name for s in approved_skills):
                        status = self.get_verification_status(skill_dir.name)
                        if status == SkillVerificationStatus.PENDING:
                            pending_skills.append({
                                "name": skill_dir.name,
                                "path": str(skill_dir / "SKILL.md"),
                                "verified": status
                            })
                        elif status == SkillVerificationStatus.REJECTED:
                            # Get risk score
                            risk = 0
                            verification_file = self.verification_dir / f"{skill_dir.name}.json"
                            if verification_file.exists():
                                try:
                                    import json
                                    vdata = json.loads(verification_file.read_text())
                                    risk = vdata.get("risk_score", 100)
                                except:
                                    pass
                            rejected_skills.append({
                                "name": skill_dir.name,
                                "path": str(skill_dir / "SKILL.md"),
                                "verified": status,
                                "risk_score": risk
                            })
        
        if not approved_skills and not pending_skills and not rejected_skills:
            return ""
        
        lines = ["<skills>"]
        
        # Approved skills (ready to use)
        if approved_skills:
            lines.append("  <!-- Approved Skills - Ready to Use -->")
            for s in approved_skills:
                name = escape_xml(s["name"])
                path = s["path"]
                desc = escape_xml(self._get_skill_description(s["name"]))
                skill_meta = self._get_skill_meta(s["name"])
                available = self._check_requirements(skill_meta)
                verified = s.get("verified", "unknown")
                risk = s.get("risk_score", 0)
                
                lines.append(f"  <skill available=\"{str(available).lower()}\" verified=\"{verified}\" risk=\"{risk}\">")
                lines.append(f"    <name>{name}</name>")
                lines.append(f"    <description>{desc}</description>")
                lines.append(f"    <location>{path}</location>")
                
                # Show missing requirements for unavailable skills
                if not available:
                    missing = self._get_missing_requirements(skill_meta)
                    if missing:
                        lines.append(f"    <requires>{escape_xml(missing)}</requires>")
                
                lines.append(f"  </skill>")
        
        # Pending skills (need approval)
        if pending_skills:
            lines.append("  <!-- Pending Skills - Require Security Scan/Approval -->")
            lines.append("  <!-- Use 'nanofolks skills approve <name>' to approve after review -->")
            for s in pending_skills:
                name = escape_xml(s["name"])
                lines.append(f"  <skill available=\"false\" verified=\"pending\" requires=\"security_approval\">")
                lines.append(f"    <name>{name} (PENDING APPROVAL)</name>")
                lines.append(f"    <description>This skill has been installed but needs security verification before use. Run security scan and approve if safe.</description>")
                lines.append(f"    <location>{s['path']}</location>")
                lines.append(f"  </skill>")
        
        # Rejected skills (dangerous - do not use)
        if rejected_skills:
            lines.append("  <!-- Rejected Skills - Security Risk Detected -->")
            lines.append("  <!-- ⚠️ These skills contain dangerous patterns. Use with extreme caution or remove. -->")
            for s in rejected_skills:
                name = escape_xml(s["name"])
                risk = s.get("risk_score", 100)
                lines.append(f"  <skill available=\"false\" verified=\"rejected\" risk=\"{risk}\">")
                lines.append(f"    <name>{name} (⚠️ SECURITY RISK)</name>")
                lines.append(f"    <description>DANGER: Security scan detected suspicious patterns. Risk score: {risk}/100. Do not use without manual review.</description>")
                lines.append(f"    <location>{s['path']}</location>")
                lines.append(f"  </skill>")
        
        lines.append("</skills>")
        
        return "\n".join(lines)
    
    def _get_missing_requirements(self, skill_meta: dict) -> str:
        """Get a description of missing requirements."""
        missing = []
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return ", ".join(missing)
    
    def _get_skill_description(self, name: str) -> str:
        """Get the description of a skill from its frontmatter."""
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name  # Fallback to skill name
    
    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content
    
    def _parse_nanofolks_metadata(self, raw: str) -> dict:
        """Parse skill metadata JSON from frontmatter (supports nanofolks and openclaw keys)."""
        try:
            data = json.loads(raw)
            return data.get("leader", data.get("openclaw", {})) if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def _check_requirements(self, skill_meta: dict) -> bool:
        """Check if skill requirements are met (bins, env vars)."""
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True
    
    def _get_skill_meta(self, name: str) -> dict:
        """Get nanofolks metadata for a skill (cached in frontmatter)."""
        meta = self.get_skill_metadata(name) or {}
        return self._parse_nanofolks_metadata(meta.get("metadata", ""))
    
    def get_always_skills(self) -> list[str]:
        """Get skills marked as always=true that meet requirements."""
        result = []
        for s in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(s["name"]) or {}
            skill_meta = self._parse_nanofolks_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or meta.get("always"):
                result.append(s["name"])
        return result
    
    def get_skill_metadata(self, name: str) -> dict | None:
        """
        Get metadata from a skill's frontmatter.
        
        Args:
            name: Skill name.
        
        Returns:
            Metadata dict or None.
        """
        content = self.load_skill(name)
        if not content:
            return None
        
        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                # Simple YAML parsing
                metadata = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip('"\'')
                return metadata
        
        return None
