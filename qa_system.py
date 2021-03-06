"""
This is the main I/O stream for the QA pipeline

FOR REMOVING SUBMODULES LATER https://gist.github.com/myusuf3/7f645819ded92bda6677

1. setup QU module
2. setup IR module
3. setup QA module
"""

import warnings

#warnings.simplefilter(action='ignore',category=UserWarning)

import json
import pandas as pd
import numpy as np
import torch
import torch.nn.functional as F
from transformers import BertTokenizer,BertForSequenceClassification,AdamW,BertConfig,get_linear_schedule_with_warmup
from lxml import etree as ET
import spacy
import scispacy
import en_core_sci_lg
from bs4 import BeautifulSoup as bs

import requests
import re
import os
from tqdm import tqdm
import json

from whoosh import index
from whoosh.fields import Schema, TEXT, IDLIST, ID, NUMERIC
from whoosh.analysis import StemmingAnalyzer
from whoosh.qparser import QueryParser

import setup
import question_understanding
import information_retrieval
import question_answering

import PubmedA

if __name__ == "__main__":
    # This ensures that all the packages are installed so that the system can work with the modules
    data_folder = 'data_modules'
    setup.setup_system(data_folder)
    index_folder_name = 'index'
    model_folder_name = 'model'
    pubmed_official_index_name = 'pubmed_articles'

    # This is for cpu support for non-NVIDEA cuda-capable machines.
    spacy.prefer_gpu()

    #initialize model
    print("Initializing model...")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    model = BertForSequenceClassification.from_pretrained(data_folder + os.path.sep + model_folder_name, cache_dir=None)

    # load in BioBERT
    print("Loading BioBERT...")
    nlp = en_core_sci_lg.load()

    index_name = input("Would you like to use 'full' index? (Y/N)\n")
    if index_name in ['Y','y','Yes','yes','yep','Yep','Yup','yup']: 
        ind_choice = 'full'
        index_var = 'full_index'
    else:
        ind_choice = 'partial'
        index_var = 'partial_index'
    print(f"Loading {ind_choice} index...")
    pubmed_article_ix = index.open_dir(data_folder + os.path.sep + index_folder_name + os.path.sep + index_var, indexname=pubmed_official_index_name)
    qp = QueryParser("abstract_text", schema=Schema(
        pmid=ID(stored=True),
        title=TEXT(stored=True),
        journal=TEXT(stored=True),
        mesh_major=IDLIST(stored=True),
        year=NUMERIC(stored=True),
        abstract_text=TEXT(stored=True, analyzer=StemmingAnalyzer())))
    n = 0
    while(True):
        user_question = input(":: Please enter your question for the BioASQ QA system or \'quit\' ::\n")
        if user_question  == 'quit': #handle end loop
            quit()
        df = pd.DataFrame({'ID':[n],'Question':user_question})
        qu_output = question_understanding.ask_and_receive(df,device,tokenizer,model,nlp)
        id, question, type, entities, query = qu_output
        if type == 'summary':
            print("Summary type questions are currently not supported. \nPlease try asking a question that can be answerend with a list, yes/no, or factoid.")
        else:
            # this takes the form (id, question, type, entities, query)
            print(f"<QU>\nID: {id}\nQuestion: {question}\nType: {type}\nEntities:{entities}\nQuery: {query}\n</QU>")
            
            query_results = information_retrieval.search(pubmed_article_ix,qp,qu_output)
            if query_results:
                top_result = query_results[0]
                print(f"Top result\n{top_result}")
                # Pass in the question ID, type, user question, and top abstract for the result  
                data_for_qa = (n, type, user_question,top_result.abstract_text)

                qa_output_dir = f'{os.getcwd()}{os.path.sep}tmp{os.path.sep}qa_output{os.path.sep}'
                results = question_answering.get_answer(data_for_qa,output_dir=qa_output_dir)
                if results:
                    print(f"Question: {user_question}\nAnswer:{results}")
                    question_answering.clear_tmp_dir()
                else:
                    print("something went wrong.")
            else:
                print("Unfortunately I do not know the answer to your question")
        
        n += 1


