import streamlit as st
import cohere

# Link Checking libraries
import validators

# Image Generation Libraries
import requests
import json

# Returns the api key if it is in secrets
# PDF access method inspired by: https://github.com/ganolan/LLM-PDF-Chatbot
def secretKey(keyName):
    if hasattr(st, "secrets"):
        if keyName in st.secrets.keys(): # Checks if the keys has COHEREAPI in it
            if st.secrets[str(keyName)] not in ["", "PASTE YOUR API KEY HERE"]: # Checks of the value corresponding to the key exists by checking if it's not empty or the default string
                return st.secrets[str(keyName)]
    
    return None # If there is no key, return None

# Decalre global variables         
global chatbot_response # Sets chatbot response to a global variable so it can be accessed whenever
chatbot_response = ""
global linkList
linkList = []
global doGen # Whether or not image generation should occure (by dfault false)
doGen = False

# Setup streamlit sidebar:
with st.sidebar:
    # Cohere api key setup
    cohereapiKey = secretKey("COHEREAPIKEY")
    cohereapiKey = st.text_input("Cohere API Key", key="cohere_api_key", type="password", value = cohereapiKey)
    st.markdown("[Get a Cohere API Key](https://dashboard.cohere.ai/api-keys)")

    # Eden api key setup
    edenapiKey = secretKey("EDENAPIKEY")
    edenapiKey = st.text_input("Eden API Key", key = "eden_api_key", type = "password", value = edenapiKey)
    st.markdown("[Get a Eden API Key](https://app.edenai.run/admin/api-settings/features-preferences)")

    # Option for image generation
    doGen = st.checkbox("Do you want a flowchart to be generated? This is a beta feature and is very nonfunctional")
    

# Title
st.title = "Python Library Searcher"

# Initialize the chat history with a greeting message
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "text": "Hello, my purpose is to provide python library names for your use. Detail your project below and I will find the apropriate libraries for you!"}]

# Display the chat messages
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["text"])



# Get user input
if prompt := st.chat_input():
    # Stop responding if the user has not added the Cohere API key

    # Logic to make if statements possible
    if cohereapiKey == None:
        cohereapiKey = False
    if edenapiKey == None:
        edenapiKey == False
    
    if not cohereapiKey and not edenapiKey:
        st.info("Please add your Cohere and Eden API key to continue.")
        st.stop()
    elif not cohereapiKey:
        st.info("Please add your Cohere API key to continue.")
        st.stop()
    elif not edenapiKey:
        st.info("Please add your Eden API key to continue")
        st.stop()

    # Cohere AI setup
    client = cohere.Client(api_key= cohereapiKey)

    # Eden AI setup
    headers = {"Authorization": "Bearer " + edenapiKey}
    url = "https://api.edenai.run/v2/image/generation" 

    # Display the user message in the chat window
    st.chat_message("user").write(prompt)

    if doGen: # The preamble is different based on whether or not image generation is chosen
        preamble = """You are a support agent who's purpose is to provide python libraries based on the requirements of the user.
                You have access to the pypi.org website which provides you with a list and description of all the python libraries
                Based on the requirements of the user, you must provide the python library best suited for their use. You must individually list each library useful for the user. After listing a library, 
                you must elaborate on why that library is chosen, explain the basic syntax of the library, always provide link to the library's documentation,
                and provide some sample code of how the user could use this library for their purpose. Whenever you make a link, 
                attach a space and a ^ symbol AFTER you finish outputting the link. After you finish generation everything above, start a new paragraph and type the symbol ~.
                After these symbols, while making sure that the instructions follow the AUP and AWS Responsible AI Policy, create instructions THAT MUST BE LESS THAN 510 CHARACTERS for a image generation AI to create a flowchart diagram that explains how a developer would use the libaries above to complete their project. Mark the end of these instructions with the symbol @. Be wary not to use the symbol ~ or the symbol @ anywhere else in the output exepct to mark the beginning and end of the instructions."""
    else: 
        preamble = """You are a support agent who's purpose is to provide python libraries based on the requirements of the user.
                You have access to the pypi.org website which provides you with a list and description of all the python libraries
                Based on the requirements of the user, you must provide the python library best suited for their use. You must individually list each library useful for the user. After listing a library, 
                you must elaborate on why that library is chosen, explain the basic syntax of the library, always provide link to the library's documentation,
                and provide some sample code of how the user could use this library for their purpose. Whenever you make a link, 
                attach a space and a ^ symbol AFTER you finish outputting the link.After you finish generating everything above, TYPE OUT a flowchart of how you would strucutre the code."""

    
    newLinkPreamble = """You are a link finder robot who's job is to find a valid link for a library. You are given a nonfunctional link to a python library and your task is to find the correct link for that library. Make sure that the link you find leads to the same content that was intended by the first link.
                    Your only output will be the correct link. You will not output anything else but that link."""
 

    # Send the user message and pdf text to the model and capture the response
    stream = client.chat_stream(chat_history=st.session_state.messages,
                            message=prompt,
                            prompt_truncation='AUTO',
                            connectors=[{"id": "web-search"}],
                            preamble=preamble)
    

    def streamResponse(chatStream): # Used to fetch chat generation
        isLink = False
        isGeneration = False
        global linkList # Call the global variable
        Link = ""
        instructions = ""
        for event in chatStream:
            if event.event_type == "text-generation":
                global chatbot_response # calls chatbot response so it can be used in this function
                chatbot_response += event.text
                
                #### LINK CHECKING ####

                # Fetches the links to double check validity
                if ("http" in event.text) or isLink == True: # Checks if http is in the output string
                    Link += str(event.text) # Adds to string variable
                    isLink = True

                if isLink == True and ("^" in event.text): # Checks when link ends. Note that I required the bot to output a ^ symbol to signify link end
                    isLink = False
                    Link = Link[:-2] # Removes the ^ symbol and space
                    Link = Link [1:] # Removes beginning space
                    if (validators.url(Link)): # Uses validator to check if link is valid
                        print("Link is valid first check")
                        linkList.append(Link)
                        yield Link
                    else: 
                        print(f"{Link} is not valid, undergoing first round regeneration")
                        newLink = client.chat(message = str(Link), # If the link is not valid, use a new chatbot to generate a new link
                                              prompt_truncation = "AUTO",
                                              connectors = [{"id" : "web-search"}],
                                              preamble = newLinkPreamble)
                        
                        if(validators.url(newLink.text)): # If the second link is in fact valid
                            print(f"{newLink.text} is valid (First round gen)")
                            linkList.append(newLink)
                            yield newLink.text
                        else:
                            yield "No Link Found" # We don't try again due to request limit. Also if the regeneration fails again it's likley that the link does not exist.
            
                    Link = ""


                #### IMAGE GENERATION ####
                # Note: We use EdenAI's api for image generation

                # Fetches the image generation instructions
                if doGen: # Only does this part if generation is enabled
                    if ("~" in event.text) or isGeneration == True: # Checks if the start key is outputted
                        instructions += str(event.text) # Adds to string variable
                        isGeneration = True
                        print("Instructions detected")
                
                    if ("@" in event.text) and isGeneration == True:
                        print("Instructions end... generating")
                        isGeneration = False
                        instructions = instructions[13:-11] # Removes the Start and End keys from the string
                        if(len(instructions) > 510):
                            while(True):
                                print("Text too long, regenerating")
                                instructions = client.chat(message = instructions,
                                                           prompt_truncation="AUTO",
                                                           preamble="Your job is to regenerate the users input so that it is LESS THAN 500 CHARACTERS while also keeping the main contents. your output will only be this regenerated content and nothign else AND IT MUST BE LESS THAN 500 CHARACTERS.").text
                                if(len(instructions) < 510):
                                    print(f"Text is now {len(instructions)}, sending to api")
                                    break
                    
                        # Starts using Eden AI (See https://www.edenai.co/post/how-to-generate-images-from-text-with-python)

                        payload = { # The JSON payload sent to Eden API
                            "providers": "amazon",
                            "text": instructions,
                            "resolution": "512x512"
                        }

                        response = requests.post(url, json=payload, headers=headers) # We use directly request the API with a JSON payload
                        genResults = json.loads(response.text) # load json and format
                        yield "\n Image Generated"
                        yield genResults
                        st.image(genResults["amazon"]["items"][0]["image_resource_url"]) # Based on the JSON responce, locate the place where the url is embedded. then display as image


                if(isLink == False and isGeneration == False): # Only allow the output to be sent to streamlink if it is not a link (so we can check if the link works)
                    yield event.text # Yield is used here so there is a stream output, this allows for continous output compatable with streamlit.
                
        
            


    st.chat_message("assistant").write_stream(streamResponse(stream))
    # Add the user prompt to the chat history
    st.session_state.messages.append({"role": "user", "text": prompt})
    
    # Add the response to the chat history
    st.session_state.messages.append({"role": "assistant", "text": chatbot_response})

with st.sidebar:
    st.markdown("List of Links:")
    for i in range(len(linkList)):
        st.markdown(linkList[i])




    



        
