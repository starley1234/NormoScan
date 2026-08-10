import re
from sqlalchemy.orm import Session
from ..models.team import Assignment, Comment
from ..models.user import User

MENTION_RE = re.compile(r"@(\w+)")

def parse_mentions(text: str):
    return MENTION_RE.findall(text)

def assign_check(db: Session, check_id: int, assignee_id: int, assigned_by: int, comment: str=None):
    # Close previous pending assignments for same check
    for a in db.query(Assignment).filter(Assignment.check_id==check_id, Assignment.status=="pending").all():
        a.status="reassigned"
    ass = Assignment(check_id=check_id, assignee_id=assignee_id, assigned_by=assigned_by, status="pending", comment=comment)
    db.add(ass)
    db.commit()
    db.refresh(ass)
    return ass

def set_review(db: Session, check_id: int, reviewer_id: int, decision: str, comment: str=None):
    # decision: approved | rejected | in_review
    ass = db.query(Assignment).filter(Assignment.check_id==check_id, Assignment.assignee_id==reviewer_id).order_by(Assignment.created_at.desc()).first()
    if not ass:
        ass = Assignment(check_id=check_id, assignee_id=reviewer_id, assigned_by=reviewer_id, status=decision)
        db.add(ass)
    else:
        ass.status = decision
        if comment:
            ass.comment = comment
    db.commit()
    db.refresh(ass)
    return ass

def add_comment(db: Session, check_id: int, author_id: int, text: str, page_number: int=None, bbox: dict=None, parent_id: int=None):
    mentions = parse_mentions(text)
    c = Comment(check_id=check_id, author_id=author_id, text=text, mentions=mentions, page_number=page_number, bbox=bbox, parent_id=parent_id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def list_comments(db: Session, check_id: int):
    return db.query(Comment).filter(Comment.check_id==check_id).order_by(Comment.created_at.asc()).all()

def list_assignments(db: Session, check_id: int=None, assignee_id: int=None):
    q = db.query(Assignment)
    if check_id:
        q = q.filter(Assignment.check_id==check_id)
    if assignee_id:
        q = q.filter(Assignment.assignee_id==assignee_id)
    return q.order_by(Assignment.created_at.desc()).all()
