#!/usr/bin/env python3
from typing import List, Tuple, Optional

from nicegui import app, context, ui, events, Client
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os
import time
from uuid import uuid4
import json

# Klassen zur Verwaltung von PDF- und Excel-Status
class InputText:
    def __init__(self):
        self.text = ""

class PDFReady:
    def __init__(self):
        self.ready = False
        self.answered = False
        self.ready_to_upload = True

class ExcelReady:  # NEU
    def __init__(self):
        self.ready = False
        self.answered = False
        self.ready_to_upload = True

inputText = InputText()
pdf_ready = PDFReady()
excel_ready = ExcelReady()  # NEU

# Authentifizierung für Verwaltungsaufgaben
passwords = {'mngmt': os.getenv('SUPERTOKEN', default="PLEASE_CHANGE_THIS_PLEASE")}
unrestricted_page_routes = {'/login', '/', '/chat', '/pdf', '/excel'}

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not app.storage.user.get('authenticated', False):
            if request.url.path in Client.page_routes.values() and request.url.path not in unrestricted_page_routes:
                app.storage.user['referrer_path'] = request.url.path
                return RedirectResponse('/login')
        return await call_next(request)

app.add_middleware(AuthMiddleware)

# Initialisierung des Frontends
def init(fastapi_app: FastAPI, jobStat, taskQueue, cfg, statistic) -> None:
    # Konfigurationen
    assi = os.getenv('ASSISTANT', default=cfg.get_config('frontend', 'assistant', default="Assistent:in"))
    you = os.getenv('YOU', default=cfg.get_config('frontend', 'you', default="Sie"))
    greeting = os.getenv('GREETING', default=cfg.get_config('frontend', 'chat-greeting', default="Willkommen beim Chat."))
    pdf_greeting = os.getenv('PDFGREETING', default=cfg.get_config('frontend', 'pdf-greeting', default="Laden Sie ein PDF hoch."))
    excel_greeting = os.getenv('EXCELGREETING', default="Laden Sie eine Excel-Datei hoch.")  # NEU

    def assign_uuid_if_missing():
        if 'chat_job' not in app.storage.user or not app.storage.user['chat_job']:
            app.storage.user['chat_job'] = uuid4()
        if 'pdf_job' not in app.storage.user or not app.storage.user['pdf_job']:
            app.storage.user['pdf_job'] = uuid4()
        if 'excel_job' not in app.storage.user or not app.storage.user['excel_job']:  # NEU
            app.storage.user['excel_job'] = uuid4()

    # Handler für Excel-Upload
    def handle_excel_upload(event: events.UploadEventArguments):  # NEU
        assign_uuid_if_missing()
        fileid = app.storage.browser['id']
        with event.content as f:
            filepath = f'/tmp/{fileid}/{event.name}'
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as file:
                file.write(f.read())
        jobStat.addJob(
            app.storage.browser['id'],
            app.storage.user['excel_job'],
            prompt='',
            custom_config=False,
            job_type='excel_processing',
        )
        job = {'token': app.storage.browser['id'], 'uuid': app.storage.user['excel_job'], 'filepath': filepath}
        try:
            taskQueue.put(job)
            excel_ready.ready = False
            excel_ready.answered = False
        except:
            jobStat.updateStatus(app.storage.browser['id'], app.storage.user['excel_job'], "failed")
        excel_ready.ready_to_upload = False
        excel_messages.refresh()

    # Nachrichtenanzeige für Excel
    @ui.refreshable
    def excel_messages() -> None:  # NEU
        assign_uuid_if_missing()
        messages: List[Tuple[str, str]] = []
        messages.append((assi, excel_greeting))
        status = jobStat.getJobStatus(app.storage.browser['id'], app.storage.user['excel_job'])
        answers = []
        if 'status' in status and status['status'] == 'processing':
            messages.append((assi, "Ihre Datei wird verarbeitet..."))
            excel_ready.ready = False
        elif 'status' in status and status['status'] == 'finished':
            excel_ready.ready = True
            if 'answer' in status:
                answers = status['answer']
        elif 'status' in status and status['status'] == 'failed':
            messages.append((assi, "Fehler bei der Verarbeitung der Datei."))
        for name, text in messages:
            ui.chat_message(text=text, name=name, sent=name == you)
        if answers:
            for answer in answers:
                ui.chat_message(text=answer, name=assi, sent=False)

    # Navigation
    def navigation():
        ui.page_title("MWICHT")
        with ui.header().classes(replace='row items-center'):
            ui.button(on_click=lambda: left_drawer.toggle(), icon='menu').props('flat color=white')
            with ui.left_drawer().classes('bg-blue-100'):
                ui.link("Home", home)
                ui.link("Chat", show)
                ui.link("PDF", pdfpage)
                ui.link("Excel", excelpage)  # Neuer Link für Excel

    # Excel-Seite
    @ui.page('/excel')
    def excelpage():  # NEU
        navigation()
        excel_messages()
        ui.upload(
            on_upload=handle_excel_upload,
            multiple=False,
            label='Upload Excel-Datei',
            max_total_size=10485760,  # 10 MB
        ).props('accept=".xlsx,.xls"').classes('max-w-full').bind_visibility_from(excel_ready, 'ready_to_upload')

        with ui.footer().classes('bg-white'):
            with ui.column().classes('w-full max-w-3xl mx-auto my-6'):
                with ui.row().classes('w-full no-wrap items-center').bind_visibility_from(excel_ready, 'ready'):
                    text = ui.textarea(placeholder="Ihre Anfrage").props('rounded outlined input-class=mx-3').props('clearable') \
                        .classes('w-full self-center').bind_value(app.storage.user, 'excel_question')
                    send_btn = ui.button(icon="send", on_click=lambda: send())

    # Weitere bestehende Seiten und Funktionen bleiben erhalten ...

    ui.run_with(
        fastapi_app,
        storage_secret=uuid4(),
    )
