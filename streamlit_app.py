# Imports
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import time
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

def initialize_sheets_client():
    """creating the connection to the evaluator's spreadsheet"""
    creds = Credentials.from_service_account_info(
        st.secrets["connections"]["eval_" + str(st.session_state.eval_id) + "_v2"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    service = build('sheets', 'v4', credentials=creds)
    spreadsheet_id = st.secrets["connections"]["eval_" + str(st.session_state.eval_id) + "_v2"]["spreadsheet"].split('/')[-2]
    return service, spreadsheet_id

# Set up the page
st.set_page_config(layout="wide")

# Function for saving evaluations in the evaluator's evaluations worksheet
def save_evaluations():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            service = st.session_state.sheets_service
            spreadsheet_id = st.session_state.spreadsheet_id
            body = {'values': st.session_state.evaluations_to_save}
            sheet = service.spreadsheets()
            start_of_range = st.session_state.evaluations_to_save[0][1]  # this is the response id of the first response to update
            
            # update range
            range_ = f"evaluations!A{start_of_range + 1}:K{start_of_range + len(st.session_state.evaluations_to_save)}"
            request = sheet.values().update(spreadsheetId=spreadsheet_id, range=range_,
                                    valueInputOption="USER_ENTERED", body=body)
            response = request.execute()
            st.session_state.evaluations_to_save = []
            return True
        except:
            if attempt == max_retries - 1:
                return False
            time.sleep(2 ** attempt)

# Mapping login data (mail address) to the evaluator id's
mapping = {
    'first-email' : 1,
    'second-email' : 2
}

# KPIs
kpis = {
    1: "Which response do you find more convincing as a rebuttal to the opinion displayed above, A or B?",
    2: "Which response evokes stronger emotions, A or B?",
    3: "Which response do you think the average social media user is more likely to find interesting to share (repost/retweet), A or B?"
}

# Login Form
def login():
    st.markdown("""
        <style>
        .main {
            overflow-y: scroll;
            padding-left: 15%;
            padding-right: 15%;
        }
        </style>
        """, unsafe_allow_html=True)
    st.title("Please enter your mail address", anchor=False)
    email = st.text_input("Enter mail address", placeholder="mail address", label_visibility="collapsed")
    st.markdown(" ") # just for creating space
    if st.button("Log in"):
        eval_id = mapping.get(email, 0)
        if eval_id == 0:
            st.error("Please check again the mail address you entered.")
        else:
            st.session_state.eval_id = eval_id
            st.session_state.eval_connection = st.connection(f"eval_{eval_id}_v2", type=GSheetsConnection)
            
            while True:
                try:
                    st.session_state.eval_comparisons = pd.DataFrame(st.session_state.eval_connection.read(worksheet="comparisons", ttl=1))
                    break
                except:
                    time.sleep(2)

            st.markdown("ok")
            st.session_state.num_evaluations = len(st.session_state.eval_comparisons)
            
            while True:
                try:
                    last_response_id = pd.DataFrame(st.session_state.eval_connection.read(worksheet="evaluations", ttl=1))['response_id'].max()
                    break
                except:
                    time.sleep(2)
            
            if last_response_id is None or pd.isna(last_response_id):
                st.session_state.last_response_id = 0
            else:
                st.session_state.last_response_id = int(last_response_id)
            st.session_state.sheets_service, st.session_state.spreadsheet_id = initialize_sheets_client()
            st.rerun()

# Main app
def main():

    st.session_state.selection = None
    st.session_state.start_time = None
    
    if 'evaluations_to_save' not in st.session_state:
        st.session_state.evaluations_to_save = []

    # If all evaluations are done - display thanks you for your effort screen
    if st.session_state.last_response_id >= st.session_state.num_evaluations:
        if st.session_state.evaluations_to_save:
            save_evaluations()
        st.html("<h1 style='text-align: center;'>You finished your evaluations! Thank you for your effort!</h1>")
        return

    if st.session_state.start_time is None:
        st.session_state.start_time = time.perf_counter()

    # Data of the current comparison tbd
    curr_comparison = st.session_state.eval_comparisons.iloc[st.session_state.last_response_id]
    base_claim = str(curr_comparison['claim'])
    left_cn = str(curr_comparison['cn_1'])
    right_cn = str(curr_comparison['cn_2'])
    kpi_id = int(curr_comparison['kpi_id'])
    kpi = kpis[kpi_id]
    diff_level = curr_comparison['diff_level']
    left_better = curr_comparison['left_better']
    # left_score = float(curr_comparison['avg_score_cn_1'])
    # right_score = float(curr_comparison['avg_score_cn_2'])

    # Progress bar
    st.markdown("""
    <style>
    .stProgress > div > div > div {
        height: 15px;
    }
    .stProgress > div > div > div > div {
        background-color: green;
    }
    </style>""", unsafe_allow_html=True)
    progress = st.session_state.last_response_id / st.session_state.num_evaluations
    st.html(f"<h6>Your progress so far: {round(progress * 100, 2)}%</h6>")
    st.progress(progress)
    
    # css code for counter-narrative boxes
    st.markdown("""
    <style>
        body {
            margin: 0 auto;
            overflow-y: scroll;
        }
        .main {
            padding-left: 5%;
            padding-right: 5%;
        }
        .equal-height-container {
            display: flex;
            align-items: stretch;
        }
        .equal-height-column {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .equal-height-paragraph {
            flex-grow: 1;
            padding: 10px;
            text-align: left;
            font-size: 150%; 
            border: 2px solid #d3d3d3;
            display: flex;
            flex-direction: column;
        }
    </style>
    """, unsafe_allow_html=True)

    st.html(f"<h4 style='text-align:center;'>Look at this claim</h4>")
    st.html(f'<p style="color:red; text-align:center; font-size: 180%;">{base_claim}</p>')
    
    st.html(f'<h4 style="text-align:center; max-width: 65%; margin: 0 auto;">{kpi}</h4>')
    
    st.html("""
    <div class="equal-height-container">
        <div class="equal-height-column">
            <h2 style='text-align:center;'>A</h2>
            <div class="equal-height-paragraph">{}</div>
        </div>
        <div style="width: 20px;"></div>
        <div class="equal-height-column">
            <h2 style='text-align:center;'>B</h2>
            <div class="equal-height-paragraph">{}</div>
        </div>
    </div>
    <p style= height:20px;> </p>
    """.format(left_cn, right_cn))

    col1, col2, col3, col4 = st.columns(4)
    
    with col2:
        if st.button(":point_left: A", use_container_width=True):
            st.session_state.selection = 1
    
    with col3:
        if st.button("B :point_right:", use_container_width=True):
            st.session_state.selection = 0
    
    # Spacing between A,B buttons to Next question button
    st.markdown("<p style= height:20px;> </p>", unsafe_allow_html=True)

    _, col, _ = st.columns(3)
    with col:
        if st.button("Next question →", use_container_width=True):
            if st.session_state.selection is not None:
                elapsed_time = int(time.perf_counter() - st.session_state.start_time)
                st.session_state.last_response_id += 1
                new_row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.last_response_id, st.session_state.eval_id, base_claim, left_cn, right_cn, diff_level, left_better, kpi_id, st.session_state.selection, elapsed_time]
                st.session_state.evaluations_to_save.append(new_row)
                st.session_state.start_time = None
                st.session_state.selection = None
                if save_evaluations():
                    st.rerun()
                else:
                    st.error("Failed to save response. Please wait for about a minute, refresh the page and try again")
            else:
                st.warning("Please select an option.")

if __name__ == "__main__":
    if 'eval_id' not in st.session_state:
        login()
    else:
        main()