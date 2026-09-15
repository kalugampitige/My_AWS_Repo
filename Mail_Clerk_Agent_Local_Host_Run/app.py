import streamlit as st
import requests
import json

# AWS Lambda Function URL
LAMBDA_URL = "https://gy5t6j6npvd3j65ydf7wzwu44q0angbe.lambda-url.us-east-1.on.aws/"

st.set_page_config(page_title="AI Mail Clerk Agent", page_icon="📧", layout="wide")

# Sidebar for controls and configuration details
st.sidebar.title("🛠️ Agent Controls")
st.sidebar.info("Connected to AWS Lambda Endpoint:\n`us-east-1`")

if st.sidebar.button("Clear Chat History", use_container_width=True):
    st.session_state.messages = []
    st.rerun()

st.title("📧 AI Mail Clerk Agent Demo")
st.caption("Paste or type an email message below to test classification, routing, and response generation.")

# Initialize chat session history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display prior chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant" and isinstance(message["content"], dict):
            # Formatted display for structured AI response
            res_data = message["content"]
            st.json(res_data)
        else:
            st.write(message["content"])

# User prompt input handling
if prompt := st.chat_input("Enter email body or subject..."):
    # Append & display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Invoke AWS Lambda Endpoint
    with st.chat_message("assistant"):
        with st.spinner("Processing email with Mail Clerk Agent (AWS Bedrock)..."):
            try:
                response = requests.post(
                    LAMBDA_URL,
                    json={"body": prompt},
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )

                if response.status_code == 200:
                    try:
                        res_json = response.json()
                        st.session_state.messages.append({"role": "assistant", "content": res_json})
                        
                        # Display nicely structured output
                        st.success("Analysis Complete")
                        st.json(res_json)
                        
                    except json.JSONDecodeError:
                        raw_text = response.text
                        st.session_state.messages.append({"role": "assistant", "content": raw_text})
                        st.write(raw_text)
                else:
                    error_msg = f"⚠️ Lambda returned status code {response.status_code}: {response.text}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

            except requests.exceptions.Timeout:
                error_msg = "⏱️ Request timed out waiting for AWS Lambda response."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
            except requests.exceptions.RequestException as e:
                error_msg = f"❌ Network Connection Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})