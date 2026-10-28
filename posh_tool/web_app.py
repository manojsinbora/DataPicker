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

    # Search in current directory
    file_path = os.path.abspath(filename)
    if not os.path.exists(file_path):
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
    if status.get("excel_path") and os.path.exists(status["excel_path"]):
        return send_file(
            status["excel_path"],
            as_attachment=True,
            download_name=status["excel_filename"],
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Look for any POSH_IC_Contacts_*.xlsx file
    xlsx_files = [f for f in os.listdir(".") if f.startswith("POSH_IC_Contacts_") and f.endswith(".xlsx")]
    if not xlsx_files:
        abort(404)

    latest_file = max(xlsx_files, key=os.path.getmtime)
    return send_file(
        os.path.abspath(latest_file),
        as_attachment=True,
        download_name=latest_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def run_web(host="127.0.0.1", port=5050, debug=False):
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run_web()

