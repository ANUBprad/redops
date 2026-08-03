"""Tests for Project domain entity."""

from app.kernel.entities.base import UUIDv7
from app.project.domain.entities import Project


def test_project_create() -> None:
    project = Project.create(
        name="Test Project",
        organization_id="org-1",
        created_by="user-1",
        description="A test project",
    )
    assert project.name == "Test Project"
    assert project.organization_id == "org-1"
    assert project.created_by == "user-1"
    assert project.is_active is True


def test_project_update() -> None:
    project = Project.create(
        name="Test Project",
        organization_id="org-1",
    )
    project.update(name="Updated Project", description="New desc")
    assert project.name == "Updated Project"
    assert project.description == "New desc"


def test_project_deactivate_activate() -> None:
    project = Project.create(
        name="Test Project",
        organization_id="org-1",
    )
    project.deactivate()
    assert project.is_active is False
    project.activate()
    assert project.is_active is True


def test_project_version_increments() -> None:
    project = Project.create(
        name="Test Project",
        organization_id="org-1",
    )
    v1 = project.version
    project.update(name="Updated")
    assert project.version > v1
