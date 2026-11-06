"""Northside Gym member portal (aws-gym-member-portal).

RDS for PostgreSQL holds members and plans (registration, login, profile page).
DynamoDB holds a simple check-in log shown on the profile page.

Mock data only: the site runs over HTTP until HTTPS is added, so never
register with a real password.
"""
import os
import socket
from datetime import date, datetime, timezone
from functools import wraps

import boto3
import psycopg
from boto3.dynamodb.conditions import Key
from flask import Flask, flash, redirect, render_template, request, session, url_for
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
# Both web servers must share the same SECRET_KEY, so a login cookie signed
# by one server is accepted by the other behind the load balancer.
app.secret_key = os.environ["SECRET_KEY"]

DB_DSN = (
    f"host={os.environ['DB_HOST']} dbname={os.environ.get('DB_NAME', 'gym')} "
    f"user={os.environ['DB_USER']} password={os.environ['DB_PASSWORD']} "
    f"sslmode={os.environ.get('DB_SSLMODE', 'require')} connect_timeout=5"
)
# Phase 1 runs with RDS only: leave CHECKINS_TABLE empty until phase 2
# creates the DynamoDB table, and the check-in card says it's coming.
CHECKINS_TABLE = os.environ.get("CHECKINS_TABLE", "")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")
SERVER_NAME = socket.gethostname()

checkins = (
    boto3.resource("dynamodb", region_name=AWS_REGION).Table(CHECKINS_TABLE)
    if CHECKINS_TABLE else None
)


def db():
    """Open a short-lived connection to RDS (fine for a demo's traffic)."""
    return psycopg.connect(DB_DSN, row_factory=dict_row)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "member_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def add_server_name():
    # Shown in the footer, so screenshots prove the ALB spreads requests.
    return {"server_name": SERVER_NAME}


@app.get("/health")
def health():
    """ALB health check: no database call, so a DB outage doesn't drain both servers."""
    return "ok", 200


@app.get("/")
def home():
    if "member_id" in session:
        return redirect(url_for("profile"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    with db() as conn:
        plans = conn.execute(
            "SELECT id, name, monthly_price FROM plans ORDER BY monthly_price"
        ).fetchall()

        if request.method == "POST":
            name = request.form["full_name"].strip()
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            plan_id = int(request.form["plan_id"])

            if len(password) < 8:
                flash("Password must be at least 8 characters.")
                return render_template("register.html", plans=plans), 400

            try:
                row = conn.execute(
                    """INSERT INTO members (full_name, email, password_hash, plan_id)
                       VALUES (%s, %s, %s, %s) RETURNING id""",
                    (name, email, generate_password_hash(password), plan_id),
                ).fetchone()
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                flash("That email is already registered. Log in instead.")
                return render_template("register.html", plans=plans), 409

            session.clear()
            session["member_id"] = row["id"]
            return redirect(url_for("profile"))

    return render_template("register.html", plans=plans)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        with db() as conn:
            member = conn.execute(
                "SELECT id, password_hash FROM members WHERE email = %s", (email,)
            ).fetchone()

        if member and check_password_hash(member["password_hash"], request.form["password"]):
            session.clear()
            session["member_id"] = member["id"]
            return redirect(url_for("profile"))

        # Same message whether the email or the password was wrong.
        flash("Email or password is incorrect.")
        return render_template("login.html"), 401

    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/profile")
@login_required
def profile():
    with db() as conn:
        member = conn.execute(
            """SELECT m.full_name, m.email, m.joined_on, m.renews_on,
                      p.name AS plan_name, p.monthly_price, p.perks
               FROM members m JOIN plans p ON p.id = m.plan_id
               WHERE m.id = %s""",
            (session["member_id"],),
        ).fetchone()

    if member is None:  # account deleted while logged in
        session.clear()
        return redirect(url_for("login"))

    visits = None  # None = DynamoDB not set up yet (phase 1)
    if checkins is not None:
        visits = checkins.query(
            KeyConditionExpression=Key("member_id").eq(str(session["member_id"])),
            ScanIndexForward=False,  # newest first
            Limit=5,
        )["Items"]

    days_left = (member["renews_on"] - date.today()).days
    return render_template("profile.html", member=member, visits=visits, days_left=days_left)


@app.post("/checkin")
@login_required
def checkin():
    if checkins is None:
        flash("Check-ins arrive in phase 2 (DynamoDB).")
        return redirect(url_for("profile"))
    checkins.put_item(Item={
        "member_id": str(session["member_id"]),
        "checked_in_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "server": SERVER_NAME,
    })
    flash("Checked in. Have a good session!")
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
