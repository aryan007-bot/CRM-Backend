"""Operational CLI for first-time setup.

A freshly migrated database has roles but no organizations or users, so nothing
can log in. These commands create the first tenant and its users without any
manual SQL:

    python -m app.cli create-org --name "Acme Recovery" --slug acme
    python -m app.cli create-user --org-slug acme --email admin@acme.com \\
        --password "ChangeMe123!" --name "Acme Admin" --role ORG_ADMIN
"""

import argparse
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.models.organization import Organization
from app.db.models.user import Role, User, UserRole
from app.db.session import SessionLocal
from app.main import SYSTEM_ROLES

VALID_ROLES = SYSTEM_ROLES


def _get_or_create_role(db, name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if not role:
        role = Role(name=name)
        db.add(role)
        db.commit()
    return role


def create_org(args: argparse.Namespace) -> int:
    with SessionLocal() as db:
        if db.scalar(select(Organization).where(Organization.slug == args.slug)):
            print(f"Organization '{args.slug}' already exists.", file=sys.stderr)
            return 1

        org = Organization(name=args.name, slug=args.slug, status="active")
        db.add(org)
        db.commit()
        db.refresh(org)
        print(f"Created organization {org.name} ({org.slug}) id={org.id}")
        return 0


def create_user(args: argparse.Namespace) -> int:
    if args.role not in VALID_ROLES:
        print(f"Invalid role '{args.role}'. Choose one of: {', '.join(VALID_ROLES)}", file=sys.stderr)
        return 1

    if len(args.password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1

    email = args.email.lower().strip()

    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == args.org_slug))
        if not org:
            print(f"Organization '{args.org_slug}' not found. Create it first.", file=sys.stderr)
            return 1

        if db.scalar(select(User).where(User.email == email)):
            print(f"A user with email '{email}' already exists.", file=sys.stderr)
            return 1

        user = User(
            organization_id=org.id,
            name=args.name,
            email=email,
            password_hash=hash_password(args.password),
            is_active=True,
        )
        db.add(user)
        db.flush()

        role = _get_or_create_role(db, args.role)
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()

        print(f"Created user {email} ({args.role}) in organization {org.slug} id={user.id}")
        return 0


def list_orgs(_: argparse.Namespace) -> int:
    with SessionLocal() as db:
        orgs = db.scalars(select(Organization).order_by(Organization.name)).all()
        if not orgs:
            print("No organizations found. Run: python -m app.cli create-org --name <name> --slug <slug>")
            return 0
        for org in orgs:
            user_count = db.scalar(
                select(func.count(User.id)).where(User.organization_id == org.id)
            )
            print(
                f"{org.slug:<24} {org.name:<32} status={org.status} users={user_count} id={org.id}"
            )
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description="AI Recovery CRM operations CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_org = sub.add_parser("create-org", help="Create an organization")
    p_org.add_argument("--name", required=True)
    p_org.add_argument("--slug", required=True)
    p_org.set_defaults(func=create_org)

    p_user = sub.add_parser("create-user", help="Create a user inside an organization")
    p_user.add_argument("--org-slug", required=True)
    p_user.add_argument("--email", required=True)
    p_user.add_argument("--password", required=True)
    p_user.add_argument("--name", required=True)
    p_user.add_argument("--role", default="ORG_ADMIN", help=f"One of: {', '.join(VALID_ROLES)}")
    p_user.set_defaults(func=create_user)

    p_list = sub.add_parser("list-orgs", help="List organizations")
    p_list.set_defaults(func=list_orgs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
