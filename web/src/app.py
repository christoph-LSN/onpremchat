from llm import build_llm
from config import config
import requests
import json
print("start")
cfg = config()
llm = build_llm(cfg)


from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any
import pickle
import os
from uuid import uuid4

from nicegui import app, ui
import frontend

import threading
import queue
import pdftools


from pdfrag import PDF_Processor





class jobStatus():

    def __init__(self):
        self.jobsByToken = {}
        self.pdfProcByToken = {}


    def addPDFProc(self,token,uuid,pdfproc):
        if token in self.pdfProcByToken:
            self.pdfProcByToken[token][uuid] = pdfproc
        else:
            self.pdfProcByToken[token] = {uuid:pdfproc}
    
    def getPDFProc(self,token,uuid):
        if token in self.pdfProcByToken and uuid in self.pdfProcByToken[token]: 
            return self.pdfProcByToken[token][uuid]
        return False

    def addJob(self,token,uuid,prompt,custom_config = False, job_type = 'chat'):
        try: 
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    self.jobsByToken[token][uuid] = {'status':'queued','prompt':self.jobsByToken[token][uuid]['prompt'] + [prompt],'answer':self.jobsByToken[token][uuid]['answer'],'custom_config':custom_config,'job_type':job_type} 
                else:
                    self.jobsByToken[token][uuid] = {'status':'queued','prompt':[prompt],'answer':[],'custom_config':custom_config,'job_type':job_type} 
            else:
                self.jobsByToken[token] = {uuid:{'status':'queued','prompt':[prompt],'answer':[],'custom_config':custom_config,'job_type':job_type}} 
        except:
            return False
    def countQueuedJobs(self):
        try:
            counter = 0
            for token in self.jobsByToken:
                for uuid in self.jobsByToken[token]:
                    if 'status' in self.jobsByToken[token][uuid]:
                        if self.jobsByToken[token][uuid]['status'] == 'queued':
                            counter +=1
            return counter
        except:
            return 0

    def removeJob(self,token,uuid):
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

    def superRemoveJob(self,uuid):
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
    
    def addAnswer(self,token,uuid,answer):
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

    def updateAnswer(self,token,uuid,answer):
        try:
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    if 'answer' in self.jobsByToken[token][uuid] and self.jobsByToken[token][uuid]['answer'] :
                        self.jobsByToken[token][uuid]['answer'][-1] = answer
                    else:
                        self.jobsByToken[token][uuid]['answer'] = [answer]
                    return True
            return False
        except Exception as error:
            print(error)
            return False
    
    
    def updateStatus(self,token,uuid,status):
        try:
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    self.jobsByToken[token][uuid]['status'] = status
                    return True
            return False
        except:
            return False
    
    def getJobStatus(self,token,uuid):
        try:
            if token in self.jobsByToken:
                if uuid in self.jobsByToken[token]:
                    status = self.jobsByToken[token][uuid]
                    status['uuid'] = uuid
                    return self.jobsByToken[token][uuid]
            return {'uuid':'','status':'','prompt':[''],'answer':['']} 
        except:
            return False
    
    def getAllJobsForToken(self,token):
        try:
            if token in self.jobsByToken:
                return self.jobsByToken[token]
            return {'':{'status':'','prompt':[''],'answer':['']}} 
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
            
  
class MainProcessor (threading.Thread):
    def __init__(self,taskLock,taskQueue,jobStat):
        super().__init__(target="MainProcessor")
       
        self.taskLock = taskLock
        self.taskQueue = taskQueue
        self.jobStat = jobStat
        
    def run(self):
        while True:
            job = self.taskQueue.get(block=True)
            self.jobStat.updateStatus(job['token'],job['uuid'],"processing")
            item = self.jobStat.getJobStatus(job['token'],job['uuid'])
            
            if 'job_type' in item and item['job_type'] == 'pdf_processing':
                if 'filepath' in job:
                    filepath = job['filepath']
                    pdfProc = self.jobStat.getPDFProc(job['token'],job['uuid'])
                    if not pdfProc:
                        pdfProc = PDF_Processor(cfg)
                        self.jobStat.addPDFProc(job['token'],job['uuid'],pdfProc)
                    pdfProc.processPDF(filepath)
                    self.jobStat.updateStatus(job['token'],job['uuid'],"finished")

            else:
                if 'job_type' in item and item['job_type'] == 'pdf_chat':
                    response = ""
                    self.jobStat.addAnswer(job['token'],job['uuid'],response)
                    pdfProc = self.jobStat.getPDFProc(job['token'],job['uuid'])
                    if not pdfProc:
                        self.jobStat.updateStatus(job['token'],job['uuid'],"failed")
                    else:
                        answer = pdfProc.askPDF(item['prompt'][-1])
                        #print(answer)
                        #answer.print_response_stream()
                        for answ in answer:
                            
                            #print(answ)
                            #res = answ#answ['choices'][0]['text'] 
                            response += answ
                            if not self.jobStat.updateAnswer(job['token'],job['uuid'],response):
                                break
                        print(response)
                        metadatas = pdfProc.getLastResponseMetaData()
                        response = response + "(vgl. "
                        for metadata in metadatas:
                            source = metadata['source'] if 'source' in metadata else '?'
                            name = metadata['file_path'] if 'file_path' in metadata else '?'
                            if '/' in name:
                                name = name.split('/')[-1]

                            response = response + name +":"+str(source)

                            
                        response = response + ")"
                        self.jobStat.updateAnswer(job['token'],job['uuid'],response)  
                        self.jobStat.updateStatus(job['token'],job['uuid'],"finished")
                        pdfProc.getLastResponseMetaData()
                else:
                    if 'job_type' in item and item['job_type'] == 'pdf_summarize':
                        pdf_proc = self.jobStat.getPDFProc(job['token'],job['uuid'])
                        self.jobStat.addAnswer(job['token'],job['uuid'],"")
                        create_callback = lambda x : self.jobStat.addAnswer(job['token'],job['uuid'],x)
                        update_callback = lambda x : self.jobStat.updateAnswer(job['token'],job['uuid'],x)
                        status_callback = lambda x : self.jobStat.updateStatus(job['token'],job['uuid'],x)
                        if 'summarizer' in job:
                            summarizer = job['summarizer']
                        else:
                            summarizer = pdftools.SimplePdfSummarizer(llm,pdf_proc,create_callback,update_callback,status_callback,cfg)
                        if not summarizer.run():
                            print('putting summarizer again')
                            self.taskQueue.put({'token':job['token'],'uuid':job['uuid'],'summarizer':summarizer})

                    else:

                        prompts = item['prompt']
                        answers = []
                        if 'answer' in item:
                            answers = item['answer']
            
                        i_p = 0
                        i_a = 0
                        instruction = ""
                        while i_p < len(prompts):
                            instruction += "USER:  " + prompts[i_p]
                            if i_a < len(answers):
                                instruction += "ASSISTANT:  " + answers[i_a]
                            i_p += 1
                            i_a += 1
            
                        if len(instruction) >= 20000:
                            instruction = instruction[-20000:]
                        chatprompt = os.getenv('CHATPROMPT',default=cfg.get_config('model','chatprompt',default="Du bist ein hilfreicher Assistent."))
                        prompt = f"{chatprompt} {instruction} ASSISTANT:"
            
                        response = ""
                        self.jobStat.addAnswer(job['token'],job['uuid'],response)
                        try:
                            if item['custom_config']:
                                answer = llm(prompt, stream=True, temperature = item['custom_config']['temperature'], max_tokens = item['custom_config']['max_tokens'], top_k=item['custom_config']['top_k'], top_p=item['custom_config']['top_p'],repeat_penalty=item['custom_config']['repeat_penalty'])
                            else:
                                answer = llm(prompt, stream=True, temperature = 0.7, max_tokens = 1024, top_k=20, top_p=0.9,repeat_penalty=1.15)
                
                            for answ in answer:
                                res = answ['choices'][0]['text'] 
                                response += res
                                if not self.jobStat.updateAnswer(job['token'],job['uuid'],response):
                                    break
                        except:
                            response = "An Error occured."
                        self.jobStat.updateAnswer(job['token'],job['uuid'],response)            
                        self.jobStat.updateStatus(job['token'],job['uuid'],"finished")





def dumpTokens(tokens):
    pickle.dump(tokens, open("/config/tokens.pickle", "wb"))

try:
    tokens = pickle.load(open("/config/tokens.pickle", "rb"))
except (OSError, IOError) as e:
    tokens = {}
    dumpTokens(tokens)

def generate_token(quota,description = ""):
    token = uuid4().hex
    tokens[token]={'quota':quota,'description':description}
    dumpTokens(tokens)
    return token

def revoke_token(token):
    if token in tokens:
        del(tokens[token])
        dumpTokens(tokens)
        return "OK"
    else:
        return "Token tot found"

def check_token(token):
    if token in tokens:
        if tokens[token]['quota'] == -1:
            return True
        if tokens[token]['quota'] > 0:
            tokens[token]['quota'] -= 1
            return True    
    return False

def token_details(token):
    if token in tokens:
        return tokens[token]
    return {'quota':0,'description':'Not existent'}

supertoken = os.getenv('SUPERTOKEN',default="PLEASE_CHANGE_THIS_PLEASE")




jobStat = jobStatus()

taskLock = threading.Lock()
taskQueue = queue.Queue(1000)

thread = MainProcessor(taskLock,taskQueue,jobStat)
thread.start()






app = FastAPI()



class Item(BaseModel):
    prompt: str
    token: str

class TokenCreation(BaseModel):
    supertoken: str
    quota: int | None = 100
    description: str | None = "unknown" 

class TokenRevoke(BaseModel):
    supertoken: str
    token: str

class Status(BaseModel):
    token: str
    uuid: str | None = "All"



@app.post("/getStatus/")
async def get_status(status: Status) -> Any:
    if status.uuid == "All":
        stat = jobStat.getAllJobsForToken(status.token)
    else:
        stat = jobStat.getJobStatus(status.token,status.uuid)
    return stat

@app.post("/getAllStatus/")
async def get_status(status: Status) -> Any:
    if status.token == supertoken:
        return jobStat.getAllStatus()
    else:
        return {"result": "Acces denied."}

@app.post("/deleteJob/")
async def get_status(status: Status) -> Any:
    if status.token == supertoken:
        stat = jobStat.superRemoveJob(status.uuid)
        
        return stat
    else:
        return {"result": "Acces denied."}
    

@app.post("/createToken/")
async def create_token(token: TokenCreation) -> Any:
    if token.supertoken == supertoken:
        token = generate_token(token.quota,token.description)
        return {"token":token}
    else:
        return {"result": "Acces denied."}
    
@app.post("/revokeToken/")
async def create_token(token: TokenRevoke) -> Any:
    if token.supertoken == supertoken:
        result = revoke_token(token.token)
        return {"result": result}
    else:
        return {"result": "Acces denied."}

@app.post("/generate/")
async def generate_text(item: Item) -> Any:
    if(check_token(item.token)):
        uuid = uuid4().hex
        jobStat.addJob(item.token,uuid,item.prompt) 
        job = {'token':item.token,'uuid':uuid}
        try:
            taskQueue.put(job)
        except:
            jobStat.updateStatus(item.token,uuid,"failed")
        result = jobStat.getJobStatus(item.token,uuid)
    else:
        result = "Access denied."
    return result

frontend.init(app,jobStat,taskQueue,cfg)