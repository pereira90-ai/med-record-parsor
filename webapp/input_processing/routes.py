from flask import render_template, request, redirect, url_for, flash, send_file
import io
import os
import tempfile
from werkzeug.utils import secure_filename
from .forms import PreprocessUploadForm
import secrets
from concurrent import futures
import pandas as pd
import pdfplumber
import time
import subprocess
from PIL import Image
from docx import Document
from odf import text, teletype
from odf.opendocument import load
from . import input_processing
from .. import socketio


JobID = str
jobs: dict[JobID, futures.Future] = {}
executor = futures.ThreadPoolExecutor(1)

job_progress = {}


@socketio.on('connect')
def handle_connect():
    print("Client Connected")

@socketio.on('disconnect')
def handle_connect():
    print("Client Disconnected")

def update_progress(job_id, progress: tuple[int, int, bool]):
    global job_progress
    job_progress[job_id] = progress    

    print("Progress: ", progress)
    socketio.emit('progress_update', {'job_id': job_id, 'progress': progress[0], 'total': progress[1]})

def failed_job(job_id):
    time.sleep(2)
    print("FAILED")
    global job_progress
    # wait for 1s
    socketio.emit('progress_failed', {'job_id': job_id})

def complete_job(job_id):
    print("COMPLETE")
    global job_progress
    socketio.emit('progress_complete', {'job_id': job_id})

def preprocess_input(job_id, file_paths):
    print("PREPROCESS")

    merged_data = []
    for i, file_path in enumerate(file_paths):
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
                merged_data.append(df)
            elif file_path.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                if not file_path.endswith('.pdf'):
                    # Convert JPG/PNG to PDF
                    pdf_output_path = os.path.join(tempfile.mkdtemp(), f"pdf_{os.path.basename(file_path)}.pdf")
                    image = Image.open(file_path)
                    image.save(pdf_output_path)
                    file_path = pdf_output_path

                # Run OCRmyPDF
                ocr_output_path = os.path.join(tempfile.mkdtemp(), f"ocr_{os.path.basename(file_path)}")
                subprocess.run(['ocrmypdf', '--force-ocr', file_path, ocr_output_path])
                with pdfplumber.open(ocr_output_path) as ocr_pdf:
                    ocr_text = ''
                    for page in ocr_pdf.pages:
                        ocr_text += page.extract_text()
                merged_data.append(pd.DataFrame({'report': [ocr_text]}))

            elif file_path.endswith('.txt'):
                with open(file_path, 'r') as f:
                    text = f.read()
                    merged_data.append(pd.DataFrame({'report': [text]}))
            elif file_path.endswith('.docx'):
                doc = Document(file_path)
                doc_text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
                merged_data.append(pd.DataFrame({'report': [doc_text]}))
            elif file_path.endswith('.odt'):
                doc = load(file_path)
                doc_text = ''
                for element in doc.getElementsByType(text.P):
                    doc_text += teletype.extractText(element)
                merged_data.append(pd.DataFrame({'report': [doc_text]}))
            else:
                print(f"Unsupported file format: {file_path}")
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            update_progress(job_id=job_id, progress=(i, len(file_paths), False))
            os.remove(file_path)
            return

        os.remove(file_path)

        update_progress(job_id=job_id, progress=(i+1, len(file_paths), True))

    merged_df = pd.concat(merged_data)
    complete_job(job_id)
    return merged_df
    merged_csv = merged_df.to_csv(index=False)

    return merged_csv
    
@input_processing.route("/download", methods=['GET'])
def download():
    job_id = request.args.get("job")
    global jobs

    job = jobs[job_id]

    if job.cancelled():
        flash(f"Job {job} was cancelled", "danger")
        return redirect(url_for('input_processing.main'))
    elif job.running():
        flash(f"Job {job} is still running", "warning")
        return redirect(url_for('input_processing.main'))
    elif job.done():
        try:
            result_df = job.result()
        except Exception as e:
            flash("Preprocessing failed / did not output anything useful!", "danger")
            return redirect(url_for('input_processing.main'))

        result_io = io.BytesIO()
        result_df.to_csv(result_io, index=False)
        result_io.seek(0)
        return send_file(
            result_io,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"report-{job_id}.csv",
        )
    else:
        flash(f"Job {job}: An unknown error occurred!", "danger")
        return redirect(url_for('input_processing.main'))
    

@input_processing.route("/", methods=['GET', 'POST'])
def main():
    print("MAIN")

    form = PreprocessUploadForm()

    if form.validate_on_submit():

        job_id = secrets.token_urlsafe()

        temp_dir = tempfile.mkdtemp()

        # Save each uploaded file to the temporary directory
        file_paths = []
        for file in form.files.data:
            if file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(temp_dir, filename)
                file.save(file_path)
                file_paths.append(file_path)

        global jobs
        jobs[job_id] = executor.submit(
            preprocess_input,
            job_id=job_id,
            file_paths=file_paths
        )

        update_progress(job_id=job_id, progress=(0, len(form.files.data)))

        flash('Upload Successful!', "success")
        return redirect(url_for('input_processing.main'))
    
    global job_progress

    return render_template("index.html", title="LLM Anonymizer", form=form, progress=job_progress)

