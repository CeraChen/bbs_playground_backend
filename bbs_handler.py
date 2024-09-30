from flask import Flask, jsonify, request
from enum import Enum
import json
import datetime
import requests

class TopicInfos:
    def __init__(self, t, w):
        self.topic_id = t
        self.warning_id = w

class Check(Enum):
    READING_LIST = TopicInfos("readingListId", "readingListWarningTopicId")
    PROGRESS_LIST = TopicInfos("progressListId", "progressWarningTopicId")
    IDEA_LIST = TopicInfos("ideaListId", None)
    PROJECT_PAGE = TopicInfos("projectPageId", "projectPageWarningTopicId") 


app = Flask(__name__)
CONFIG = json.load(open("./api_config.json", "r", encoding="utf-8"))



@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Access-Control-Allow-Origin'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    return response



@app.route('/api/load', methods=['POST'])
def load_content():  
    reading_notes = {}

    config = None
    with open("./config.json", "r", encoding="utf-8") as fd:
        config = json.load(fd)
    config = config["modules"]["GroupBBS"]

    USERS = config["wechat2topicId"]
    TARGET_CHECK = Check.READING_LIST.value

    check_id = TARGET_CHECK.topic_id
    HIGH_NUMBER = 999999 #jump to last post, unless there is more than this number of posts... (unlikely)
    
    for i, (user, uinfo) in enumerate(USERS.items()):
        reading_note = {}
        print(f"{i} / {len(USERS)} : {user}", end="\r", flush=True)
        
        if("skip" in uinfo.keys() and uinfo["skip"]):
            print("              ", end="\r")
            print(f"SKIP\t{user}")
            continue
        topicId = uinfo[check_id]
        try:                
            host = CONFIG["VisBot"]["HOST"]
            api_key = CONFIG["VisBot"]["API_KEY"]
            user_name = CONFIG["VisBot"]["USER_NAME"]
            
            url = f"{host}/t/{topicId}/{HIGH_NUMBER}.json"
            r = requests.get(
                url=url, 
                headers={
                    "Api-Key": api_key,
                    "Api-Username": user_name,
                }, 
                data=""
            )
        except:
            print(f"Error at {user} / {uinfo['bbsUsername']} -\t server status: {r.status_code}")
            continue
        #At this point request should have passed 
        
        # to get the latest reading note
        try: 
            count = -1
            user_name = r.json()["post_stream"]["posts"][count]["username"]
            while uinfo['bbsUsername'] != user_name:
                count -= 1
                print("SKIP other comment: {} -> {}".format(user_name, uinfo['bbsUsername']))
                
            topic_id = r.json()["post_stream"]["posts"][count]["topic_id"]
            name = r.json()["post_stream"]["posts"][count]["name"]
            note = r.json()["post_stream"]["posts"][count]["cooked"]
            
            date_str_iso8601 = r.json()["post_stream"]["posts"][count]["updated_at"]
            updated_date = date_str_iso8601[5:10] + " " + date_str_iso8601[11:19]
            if updated_date[0] == "0":
                updated_date = updated_date[1:]
                
            print("Obtained {}'s note".format(name))
            reading_note["name"] = name
            reading_note["content"] = note
            reading_note["update"] = updated_date
            reading_note["topic_id"] = topic_id
            
            reading_notes[str(i)] = reading_note
            
        except Exception as e:
            print(e)
            continue
    
    print("FINISHED!")
    # print(reading_notes)     
    return reading_notes



@app.route('/api/send', methods=['POST'])
def send_content():
    try:
        data = request.json
    except Exception as e:
        print(e)
        return {"result": False, "info": "Failed to post the comment.", "warning": ""}
    
    topic_id = data["topic_id"]
    message = data["message"]
    user = None if "user" not in data.keys() else data["user"]
    print(user)
    
    user_warning = ""    
    try:            
        host = CONFIG[user]["HOST"]
        api_key = CONFIG[user]["API_KEY"]
        user_name = CONFIG[user]["USER_NAME"]
    except:
        if user is None:
            user_warning = "No reviewer user assigned. "
        else:
            user_warning = "Invalid user {} assigned. ".format(user)
        user = "VisBot"
        user_warning += "Switch to default reviewer user {} instead.".format(user)
        
        host = CONFIG[user]["HOST"]
        api_key = CONFIG[user]["API_KEY"]
        user_name = CONFIG[user]["USER_NAME"]
    
    print(user_name, "to post")    
    r = requests.post(
        url=f"{host}/posts.json",
        headers={
            "Api-Key": api_key,
            "Api-Username": user_name,
        }, 
        data={"topic_id": topic_id, "raw": message}
    )   
    
    if r.status_code == 200:
        return {"result": True, "info": "Comment posted successfully!", "warning": user_warning}
    else:
        return {"result": False, "info": "Failed to post the comment. [status code: {}]".format(r.status_code), "warning": user_warning}




if __name__ == '__main__':
    app.run()