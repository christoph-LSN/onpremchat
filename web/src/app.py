from llm import build_llm
from config import config
import requests
import json
print("start")
cfg = config()

import os

from llama_index.llms import LlamaCPP

n_ctx = int(os.getenv('NUMBER_OF_TOKENS', default=cfg.get_config('model', 'number_of_tokens', default=4096)))
llm2 = LlamaCPP(
    model_path=os.getenv('MODEL_BIN_PATH', default=cfg.get_config('model', 'model_bin_path', default="/models/em_german_leo_mistral.Q5_K_S.gguf")),
    temperature=0.1,
    max_new_tokens=512,
    context_window=n_ctx,
    model_kwargs={"n_gpu_layers": int(os.getenv('GPU_LAYERS', default=cfg.get_config('model', 'gpu_layers', default=0))), "n_ctx": n_ctx},
    verbose=True,
)

llm = llm2

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any
import pickle

from uuid import uuid4

from nicegui import app, ui
import frontend

import threading
import queue
import pdftools

from pdfrag import PDF_Processor
from excel_processor import ExcelProcessor  # Import des ExcelProcessors
from statistics import Statistic

from promptutils import PromptFomater

class jobStatus():
    def __init__(self):
        self.jobsByToken = {}
        self.pdfProcByToken = {}

    def addPDFProc(self, token, uuid, pdfproc):
        if token in self.pdfProcByToken:
            self.pdfProcByToken[token][uuid] = pdfproc
        else:
            self.pdfProcByToken[token] = {uuid: pdfproc}

    def getPDFProc(self, token, uuid):
        if token in self.pdfProcByToken and uuid in self.pdfProcByToken[token]:
            return self.pdfProcByToken[token][uuid]
        return False

    def addJob(self, token, uuid, prompt, custom_config=False, job_type='chat'):
        try:
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    self.jobsByToken[token][uuid] = {
                        'status': 'queued',
                        'prompt': self.jobsByToken[token][uuid]['prompt'] + [prompt],
                        'answer': self.jobsByToken[token][uuid]['answer'],
                        'custom_config': custom_config,
                        'job_type': job_type
                    }
                else:
                    self.jobsByToken[token][uuid] = {
                        'status': 'queued',
                        'prompt': [prompt],
                        'answer': [],
                        'custom_config': custom_config,
                        'job_type': job_type
                    }
            else:
                self.jobsByToken[token] = {
                    uuid: {'status': 'queued', 'prompt': [prompt], 'answer': [], 'custom_config': custom_config, 'job_type': job_type}
                }
        except:
            return False

    def countQueuedJobs(self):
        try:
            counter = 0
            for token in self.jobsByToken:
                for uuid in self.jobsByToken[token]:
                    if 'status' in self.jobsByToken[token][uuid]:
                        if self.jobsByToken[token][uuid]['status'] == 'queued':
                            counter += 1
            return counter
        except:
            return 0

    def removeJob(self, token, uuid):
        try:
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    del self.jobsByToken[token][uuid]
                    if token in self.pdfProcByToken and uuid in self.pdfProcByToken[token]:
                        del self.pdfProcByToken[token][uuid]
                    return True
            return False
        except:
            return False

    def superRemoveJob(self, uuid):
        try:
            if uuid == 'All':
                self.jobsByToken = {}
                self.pdfProcByToken = {}
                return True
            else:
                for token in self.jobsByToken:
                    if uuid in self.jobsByToken[token]:
                        del self.jobsByToken[token][uuid]
                        return True
                return False
        except:
            return False

    def addAnswer(self, token, uuid, answer):
        try:
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    if 'answer' in self.jobsByToken[token][uuid]:
                        self.jobsByToken[token][uuid]['answer'].append(answer)
                    else:
                        self.jobsByToken[token][uuid]['answer'] = [answer]
                    return True
            return False
        except:
            return False

    def updateAnswer(self, token, uuid, answer):
        try:
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    if 'answer' in self.jobsByToken[token][uuid] and self.jobsByToken[token][uuid]['answer']:
                        self.jobsByToken[token][uuid]['answer'][-1] = answer
                    else:
                        self.jobsByToken[token][uuid]['answer'] = [answer]
                    return True
            return False
        except Exception as error:
            print(error)
            return False

    def updateStatus(self, token, uuid, status):
        try:
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    self.jobsByToken[token][uuid]['status'] = status
                    return True
            return False
        except:
            return False

    def getJobStatus(self, token, uuid):
        try:
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    status = self.jobsByToken[token][uuid]
                    status['uuid'] = uuid
                    return self.jobsByToken[token][uuid]
            return {'uuid': '', 'status': '', 'prompt': [''], 'answer': ['']}
        except:
            return False

    def getAllJobsForToken(self, token):
        try:
            if token in self.jobsByToken:
                return self.jobsByToken[token]
            return {'': {'status': '', 'prompt': [''], 'answer': ['']}}
        except:
            return False

    def getAllStatus(self):
        try:
            result = {}
            for token in self.jobsByToken:
                result[token] = {}
                for uuid in self.jobsByToken[token]:
                    result[token][uuid] = {}
                    if 'status' in self.jobsByToken[token][uuid]:
                        result[token][uuid]['status'] = self.jobsByToken[token][uuid]['status']
            return result
        except:
            return False


class MainProcessor(threading.Thread):
    def __init__(self, taskLock, taskQueue, jobStat, statistic):
        super().__init__(target="MainProcessor")

        self.taskLock = taskLock
        self.taskQueue = taskQueue
        self.jobStat = jobStat
        self.statistic = statistic

    def run(self):
        while True:
            job = self.taskQueue.get(block=True)
            self.jobStat.updateStatus(job['token'], job['uuid'], "processing")
            item = self.jobStat.getJobStatus(job['token'], job['uuid'])
            self.statistic.updateQueueSize(self.jobStat.countQueuedJobs())

            if 'job_type' in item and item['job_type'] == 'pdf_processing':
                # PDF Verarbeitung
                pass
            elif 'job_type' in item and item['job_type'] == 'excel_processing':
                # Excel Verarbeitung
                pass

# Der Rest bleibt wie gehabt ...
