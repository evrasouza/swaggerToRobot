from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import uvicorn
import os
import json
import yaml
from jinja2 import Template
from typing import Dict
from tempfile import NamedTemporaryFile

app = FastAPI()

# Template base para gerar testes em Robot Framework com RequestsLibrary
robot_template = Template("""*** Settings ***
Library    RequestsLibrary

*** Variables ***
${BASE_URL}    {{ base_url }}

*** Test Cases ***
{% for ep in endpoints %}{{ ep.method|upper }} {{ ep.path }}
    [Tags]    auto
    Create Session    api    ${BASE_URL}
    {{ ep.method|title }}    api    {{ ep.full_path }}{% if ep.body %}    data={{ ep.body|tojson }}{% endif %}
    Status Should Be    200

{% endfor %}""")

def parse_swagger(swagger: Dict):
    base_url = swagger.get("servers", [{"url": "http://localhost"}])[0]["url"]
    paths = swagger.get("paths", {})
    endpoints = []

    for path, methods in paths.items():
        for method, config in methods.items():
            ep = {
                "method": method,
                "path": path,
                "full_path": path.replace("{", "${").replace("}", "}"),
                "body": config.get("requestBody", {}).get("content", {}).get("application/json", {}).get("example", {})
            }
            endpoints.append(ep)

    return base_url, endpoints

@app.post("/generate")
async def generate_robot(swagger_file: UploadFile = File(...)):
    ext = os.path.splitext(swagger_file.filename)[-1].lower()
    content = await swagger_file.read()
    swagger = yaml.safe_load(content) if ext in [".yaml", ".yml"] else json.loads(content)

    base_url, endpoints = parse_swagger(swagger)
    robot_content = robot_template.render(base_url=base_url, endpoints=endpoints)

    with NamedTemporaryFile(delete=False, suffix=".robot", mode="w") as tmp:
        tmp.write(robot_content)
        tmp_path = tmp.name

    return FileResponse(tmp_path, media_type='text/plain', filename="generated_tests.robot")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

