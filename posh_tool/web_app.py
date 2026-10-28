"""
Flask Web Application for POSH & Company Research Tool.
Zero AI, 100% deterministic public data research web interface.
"""

import os
from flask import Flask, request, jsonify, render_template, send_file, abort
from .web_manager import WebTaskManager

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)

manager = WebTaskManager()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/start", methods=["POST"])
def start_task():
    data = request.get_json() or {}
    city = data.get("city", "").strip()
    area = data.get("area", "Whole city").strip()
    count = data.get("count", 25)
    industry = data.get("industry", "Any").strip()
    require_phone = data.get("require_phone", "optional").strip().lower()
    if require_phone not in ["mandatory", "optional"]:
        require_phone = "optional"
    batch_size = data.get("batch_size", 25)
    auto_continue = data.get("auto_continue", True)

    if not city:
        return jsonify({"success": False, "error": "City name is required"}), 400

    try:
        count = int(count)
        if count <= 0:
            count = 25
    except ValueError:
        count = 25

    started = manager.start_task(
        city=city,
        area=area,
        count=count,
        industry=industry,
        require_phone=require_phone,
        batch_size=batch_size,
        auto_continue=auto_continue
    )

    if not started:
        return jsonify({"success": False, "error": "A research task is already running"}), 409

    return jsonify({"success": True, "message": "Research task started successfully"})


@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify(manager.get_status())


@app.route("/api/continue", methods=["POST"])
def continue_task():
    resumed = manager.continue_batch()
    return jsonify({"success": resumed})


@app.route("/api/stop", methods=["POST"])
def stop_task():
    stopped = manager.stop_task()
    return jsonify({"success": stopped})


@app.route("/api/download/<filename>", methods=["GET"])
def download_file(filename):
    # Security check: filename must match expected pattern
    if not filename.endswith(".xlsx") or "/" in filename or "\\" in filename:
        abort(400)

    # Search in current directory or manager path
    file_path = os.path.abspath(filename)
    if not os.path.exists(file_path):
        if manager.excel_path and os.path.exists(manager.excel_path):
            file_path = manager.excel_path
        else:
            abort(404)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/api/download-latest", methods=["GET"])
def download_latest():
    status = manager.get_status()
    if status.get("excel_path") and os.path.exists(status["excel_path"]) and os.path.getsize(status["excel_path"]) > 0:
        return send_file(
            status["excel_path"],
            as_attachment=True,
            download_name=status.get("excel_filename") or "POSH_IC_Contacts.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Look for any POSH_IC_Contacts_*.xlsx file with non-zero size
    xlsx_files = [
        f for f in os.listdir(".") 
        if f.startswith("POSH_IC_Contacts_") and f.endswith(".xlsx") and os.path.getsize(f) > 0
    ]
    if xlsx_files:
        latest_file = max(xlsx_files, key=os.path.getmtime)
        return send_file(
            os.path.abspath(latest_file),
            as_attachment=True,
            download_name=latest_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Guarantee: even if no file exists yet, generate and deliver a clean template Excel
    from .excel_exporter import ExcelExporter
    exp = ExcelExporter(city="General")
    created_path = exp.export_batch([], "Whole city", "Any", 25, 1, [], [])
    return send_file(
        created_path,
        as_attachment=True,
        download_name=exp.filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def run_web(host="127.0.0.1", port=5050, debug=False):
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run_web()

