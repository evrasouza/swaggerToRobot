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

robot_template = Template("""*** Settings ***
Library    RequestsLibrary
Library    Collections

*** Variables ***
${BASE_URL}    {{ base_url }}

*** Test Cases ***
{% for ep in endpoints %}{{ ep.method|upper }} {{ ep.path }}
    [Tags]    auto
    Create Session    api    ${BASE_URL}
{% if ep.body %}
    &{body}=    Create Dictionary    {% for k, v in ep.body.items() %}{{ k }}={{ v }}{% if not loop.last %}    {% endif %}{% endfor %}
    {{ ep.method|title }}    api    {{ ep.full_path }}    json=${body}
{% else %}
    {{ ep.method|title }}    api    {{ ep.full_path }}
{% endif %}
    Status Should Be    200

{% endfor %}""")

def get_dummy_value(prop_type):
    if prop_type == "string":
        return "example"
    elif prop_type == "integer":
        return 123
    elif prop_type == "boolean":
        return True
    elif prop_type == "array":
        return ["item1", "item2"]
    elif prop_type == "object":
        return {"key": "value"}
    else:
        return "<value>"

def extract_body(schema: Dict) -> Dict:
    if not schema:
        return {}

    properties = schema.get("properties", {})
    body = {}

    for k, v in properties.items():
        prop_type = v.get("type", "string")
        body[k] = get_dummy_value(prop_type)

    return body

def parse_swagger(swagger: Dict):
    base_url = swagger.get("servers", [{"url": "http://localhost"}])[0]["url"]
    paths = swagger.get("paths", {})
    endpoints = []

    for path, methods in paths.items():
        for method, config in methods.items():
            body = None
            if "requestBody" in config:
                content = config["requestBody"].get("content", {})
                json_data = content.get("application/json", {})
                body = json_data.get("example")

                if not body:
                    schema = json_data.get("schema", {})
                    body = extract_body(schema)

            full_path = path
            for param in config.get("parameters", []):
                if param.get("in") == "path":
                    name = param["name"]
                    full_path = full_path.replace("{" + name + "}", "${" + name.upper() + "}")

            ep = {
                "method": method,
                "path": path,
                "full_path": full_path,
                "body": body or {}
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
