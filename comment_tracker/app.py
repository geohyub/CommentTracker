"""Flask web application for Comment Tracker GUI."""

import io
import json
import os
import tempfile
from datetime import datetime

from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, flash, send_file)

from . import db as database
from . import importer
from . import search
from .analytics import project_stats, client_stats, trend, distribution, recurring, bsc
from .ll import scanner, flagger, exporter
from .models import LABELS_KO, VALID_COMMENT_TYPES
from .reporters import excel


def create_app(db_path=None):
    """Create and configure the Flask application."""
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), "templates"),
                static_folder=os.path.join(os.path.dirname(__file__), "static"))
    app.secret_key = os.urandom(24)
    app.config["DB_PATH"] = db_path

    # Initialize database
    database.init_db(db_path)

    app.jinja_env.globals['LABELS_KO'] = LABELS_KO
    app.jinja_env.globals['VALID_COMMENT_TYPES'] = VALID_COMMENT_TYPES

    def get_db():
        return app.config["DB_PATH"]

    # ─── Dashboard ──────────────────────────────────────────────
    @app.route("/")
    def dashboard():
        info = database.get_db_info(get_db())
        projects = project_stats.get_all_projects_summary(get_db())
        clients = client_stats.get_all_clients_summary(get_db())

        # Recent comments
        recent, _ = search.list_comments(limit=10, db_path=get_db())

        # Category distribution for chart
        dist = distribution.get_category_distribution(db_path=get_db())

        return render_template("dashboard.html",
                               info=info, projects=projects,
                               clients=clients, recent=recent,
                               distribution=dist)

    # ─── Import ─────────────────────────────────────────────────
    @app.route("/import", methods=["GET", "POST"])
    def import_page():
        if request.method == "GET":
            return render_template("import.html")

        # Handle file upload (single or multiple)
        files = request.files.getlist("file")
        if not files or not files[0].filename:
            flash("파일을 선택해주세요.", "error")
            return render_template("import.html")

        update_mode = request.form.get("update") == "on"
        results = []
        errors = []

        for file in files:
            try:
                content = file.read().decode("utf-8")
                filename = file.filename.lower()

                if filename.endswith(".json"):
                    proj_data, batch_data, comments_data = importer.parse_json(content)
                elif filename.endswith(".csv"):
                    # For CSV, metadata must be provided via form
                    proj_data = {
                        "project_code": request.form.get("project_code", "").strip(),
                        "project_name": request.form.get("project_name", "").strip(),
                        "client": request.form.get("client", "").strip(),
                        "report_type": request.form.get("report_type", "").strip() or None,
                        "survey_type": request.form.get("survey_type", "").strip() or None,
                    }
                    batch_data = {
                        "revision": request.form.get("revision", "").strip(),
                        "reviewer": request.form.get("reviewer", "").strip() or None,
                        "received_date": request.form.get("received_date", "").strip() or None,
                        "source_file": file.filename,
                        "comment_type": request.form.get("comment_type", "General"),
                    }
                    proj_data, batch_data, comments_data = importer.parse_csv(
                        content, proj_data, batch_data
                    )
                else:
                    errors.append(f"{file.filename}: 지원하지 않는 파일 형식 (JSON/CSV만 가능)")
                    continue

                result = importer.import_data(
                    proj_data, batch_data, comments_data,
                    db_path=get_db(), update=update_mode
                )
                results.append(result)

            except importer.ImportError as e:
                errors.append(f"{file.filename}: {str(e)}")
            except Exception as e:
                errors.append(f"{file.filename}: {str(e)}")

        # Flash results
        if results:
            total_comments = sum(r["total"] for r in results)
            if len(results) == 1:
                r = results[0]
                flash(
                    f"{r['total']}건 코멘트 임포트 완료 "
                    f"[{r['comment_type']}] "
                    f"{r['project_code']} {r['revision']}",
                    "success"
                )
            else:
                flash(
                    f"{len(results)}개 파일에서 총 {total_comments}건 코멘트 임포트 완료",
                    "success"
                )

        for err in errors:
            flash(err, "error")

        if results:
            return redirect(url_for("dashboard"))
        return render_template("import.html")

    # ─── Comments ───────────────────────────────────────────────
    @app.route("/comments")
    def comments_page():
        page = request.args.get("page", 1, type=int)
        per_page = 30
        sort = request.args.get("sort", "id")
        sort_dir = request.args.get("dir", "desc")
        filters = {}
        for key in ["project", "client", "revision", "category", "status", "assignee", "comment_type"]:
            val = request.args.get(key)
            if val:
                filters[key] = val

        comments, total = search.list_comments(
            filters=filters if filters else None,
            limit=per_page,
            offset=(page - 1) * per_page,
            sort=sort,
            sort_dir=sort_dir,
            db_path=get_db()
        )
        options = search.get_filter_options(get_db())
        total_pages = (total + per_page - 1) // per_page

        return render_template("comments.html",
                               comments=comments, total=total,
                               page=page, total_pages=total_pages,
                               filters=filters, options=options,
                               sort=sort, sort_dir=sort_dir)

    @app.route("/comment/<int:comment_id>")
    def comment_detail(comment_id):
        comment = search.get_comment_detail(comment_id, get_db())
        if not comment:
            flash("Comment not found", "error")
            return redirect(url_for("comments_page"))

        # Find similar comments
        similar = search.find_similar(comment["comment_text"], limit=5, db_path=get_db())
        # Exclude self
        similar = [s for s in similar if s["id"] != comment_id]

        return render_template("comment_detail.html",
                               comment=comment, similar=similar)

    # ─── Search ─────────────────────────────────────────────────
    @app.route("/search")
    def search_page():
        query = request.args.get("q", "").strip()
        results = []
        if query:
            filters = {}
            for key in ["client", "project", "category", "status", "comment_type"]:
                val = request.args.get(key)
                if val:
                    filters[key] = val
            try:
                results = search.full_text_search(
                    query, filters=filters if filters else None,
                    db_path=get_db()
                )
            except Exception:
                flash("Search query error. Try simpler terms.", "warning")

        options = search.get_filter_options(get_db())
        return render_template("search.html",
                               query=query, results=results, options=options)

    @app.route("/similar")
    def similar_page():
        text = request.args.get("text", "").strip()
        results = []
        if text:
            results = search.find_similar(text, limit=15, db_path=get_db())
        return render_template("similar.html", text=text, results=results)

    # ─── Analytics ──────────────────────────────────────────────
    @app.route("/analytics")
    def analytics_page():
        projects = project_stats.get_all_projects_summary(get_db())
        clients = client_stats.get_all_clients_summary(get_db())
        dist = distribution.get_category_distribution(db_path=get_db())
        cat_trend = trend.get_category_trend_by_period(db_path=get_db())
        themes = recurring.find_recurring_themes(db_path=get_db())

        return render_template("analytics.html",
                               projects=projects, clients=clients,
                               distribution=dist, category_trend=cat_trend,
                               themes=themes)

    @app.route("/analytics/project/<project_code>")
    def project_analytics(project_code):
        stats = project_stats.get_project_stats(project_code, get_db())
        if not stats:
            flash("Project not found", "error")
            return redirect(url_for("analytics_page"))

        trend_data = trend.get_project_trend(project_code, db_path=get_db())
        dist = distribution.get_category_distribution(
            project_code=project_code, db_path=get_db()
        )

        return render_template("project_detail.html",
                               project=stats, trend=trend_data,
                               distribution=dist)

    @app.route("/analytics/client/<client_name>")
    def client_analytics(client_name):
        stats = client_stats.get_client_stats(client_name, get_db())
        if not stats:
            flash("Client not found", "error")
            return redirect(url_for("analytics_page"))

        dist = distribution.get_category_distribution(
            client=client_name, db_path=get_db()
        )
        cat_trend = trend.get_category_trend_by_period(
            client=client_name, db_path=get_db()
        )

        return render_template("client_detail.html",
                               client=stats, distribution=dist,
                               category_trend=cat_trend)

    # ─── BSC ────────────────────────────────────────────────────
    @app.route("/bsc")
    def bsc_page():
        options = search.get_filter_options(get_db())
        assignee = request.args.get("assignee")
        year = request.args.get("year")
        date_from = request.args.get("from")
        date_to = request.args.get("to")

        report = None
        if assignee:
            report = bsc.get_bsc_report(
                assignee, year=year, date_from=date_from,
                date_to=date_to, db_path=get_db()
            )

        return render_template("bsc.html", report=report,
                               options=options, current_assignee=assignee,
                               current_year=year)

    # ─── L&L ────────────────────────────────────────────────────
    @app.route("/ll")
    def ll_page():
        flags = flagger.list_ll_flags(db_path=get_db())
        return render_template("ll.html", flags=flags)

    @app.route("/ll/scan")
    def ll_scan():
        candidates = scanner.scan_for_ll_candidates(get_db())
        return render_template("ll_scan.html", candidates=candidates)

    @app.route("/ll/flag", methods=["POST"])
    def ll_flag():
        try:
            comment_id = int(request.form.get("comment_id"))
            ll_type = request.form.get("ll_type")
            summary = request.form.get("ll_summary", "").strip() or None
            action = request.form.get("ll_action", "").strip() or None

            flag_id = flagger.flag_comment(
                comment_id, ll_type, summary=summary, action=action,
                db_path=get_db()
            )
            flash(f"Comment #{comment_id} flagged as '{ll_type}' (Flag #{flag_id})", "success")
        except ValueError as e:
            flash(str(e), "error")

        return redirect(request.referrer or url_for("ll_page"))

    @app.route("/ll/unflag/<int:flag_id>", methods=["POST"])
    def ll_unflag(flag_id):
        flagger.unflag_comment(flag_id, get_db())
        flash("L&L flag removed", "success")
        return redirect(url_for("ll_page"))

    @app.route("/ll/export")
    def ll_export():
        data = exporter.export_ll_data(db_path=get_db())
        return jsonify(data)

    # ─── Export ──────────────────────────────────────────────────
    @app.route("/export/excel")
    def export_excel():
        client = request.args.get("client")
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            excel.generate_stats_report(tmp.name, client=client, db_path=get_db())
            return send_file(
                tmp.name,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"comment_tracker_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )

    @app.route("/export/comments")
    def export_comments():
        filters = {}
        for key in ["project", "client", "revision", "category", "status", "assignee", "comment_type"]:
            val = request.args.get(key)
            if val:
                filters[key] = val

        comments, _ = search.list_comments(
            filters=filters if filters else None,
            limit=10000,
            db_path=get_db()
        )

        fmt = request.args.get("format", "json")
        if fmt == "json":
            return jsonify(comments)
        else:
            # CSV
            if not comments:
                return "No data", 404
            output = io.StringIO()
            import csv
            writer = csv.DictWriter(output, fieldnames=comments[0].keys())
            writer.writeheader()
            writer.writerows(comments)
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype="text/csv",
                as_attachment=True,
                download_name=f"comments_export_{datetime.now().strftime('%Y%m%d')}.csv"
            )

    @app.route("/ll/export/download")
    def ll_export_download():
        data = exporter.export_ll_data(db_path=get_db())
        content = json.dumps(data, indent=2, ensure_ascii=False)
        return send_file(
            io.BytesIO(content.encode("utf-8")),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"ll_export_{datetime.now().strftime('%Y%m%d')}.json"
        )

    # ─── API endpoints ──────────────────────────────────────────
    @app.route("/api/db-info")
    def api_db_info():
        return jsonify(database.get_db_info(get_db()))

    @app.route("/api/stats/overview")
    def api_stats_overview():
        info = database.get_db_info(get_db())
        dist = distribution.get_category_distribution(db_path=get_db())
        return jsonify({"info": info, "distribution": dist})

    # ─── Batch Management ─────────────────────────────────────
    @app.route("/batches")
    def batches_page():
        batches = database.list_batches(get_db())
        return render_template("batches.html", batches=batches)

    @app.route("/batch/<int:batch_id>")
    def batch_detail(batch_id):
        batch, comments = database.get_batch_detail(batch_id, get_db())
        if not batch:
            flash("배치를 찾을 수 없습니다.", "error")
            return redirect(url_for("batches_page"))
        return render_template("batch_detail.html", batch=batch, comments=comments)

    @app.route("/batch/<int:batch_id>/delete", methods=["POST"])
    def batch_delete(batch_id):
        info = database.delete_batch(batch_id, get_db())
        if info:
            flash(
                f"배치 삭제 완료: {info['project_code']} [{info['comment_type']}] "
                f"{info['revision']} ({info['source_file']}) "
                f"— {info['deleted_comments']}건 코멘트 삭제",
                "success"
            )
        else:
            flash("배치를 찾을 수 없습니다.", "error")
        return redirect(url_for("batches_page"))

    # ─── Projects Management ────────────────────────────────────
    @app.route("/projects")
    def projects_page():
        sort_by = request.args.get("sort", "date")
        projects = project_stats.get_all_projects_summary(get_db(), sort_by=sort_by)
        return render_template("projects.html", projects=projects, sort_by=sort_by)

    # ─── Settings / DB Info ─────────────────────────────────────
    @app.route("/settings")
    def settings_page():
        info = database.get_db_info(get_db())
        return render_template("settings.html", info=info)

    return app
