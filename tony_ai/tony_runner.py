"""Tony's issue-based agent team: proposals only, no code execution or merges."""
import os
import requests
from agents import Agent, Runner

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
http = requests.Session()
http.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})

def github(method, route, **kwargs):
    result = http.request(method, "https://api.github.com" + route, timeout=30, **kwargs)
    result.raise_for_status()
    return result.json() if result.content else {}

coder = Agent(
    name="Coding Agent",
    instructions="Design safe UAV software solutions for Python, C++, OpenCV, ArduPilot, and MAVLink. Produce implementation proposals, not unverified claims of code execution."
)
tester = Agent(
    name="Testing Agent",
    instructions="Independently review UAV software proposals, risks, edge cases, and simulator test plans. Clearly distinguish proposed tests from tests actually executed."
)
tony = Agent(
    name="Tony",
    instructions="Coordinate Omar's fixed-wing UAV engineering tasks. Ask the Coding Agent for implementation and the Testing Agent for critical review. Return: proposed implementation, QA analysis, next task, and Omar approval needed. Never claim to have run tests, committed changes or deployed flight software.",
    tools=[
        coder.as_tool(tool_name="coding_agent", tool_description="Develop a UAV coding proposal"),
        tester.as_tool(tool_name="testing_agent", tool_description="Critically review the proposal and propose tests"),
    ],
)

def main():
    issues = github("GET", f"/repos/{REPO}/issues",
                    params={"state": "open", "labels": "tony-ready", "per_page": 30})
    for issue in issues:
        if "pull_request" in issue or any(label["name"] == "tony-done" for label in issue["labels"]):
            continue
        number = issue["number"]
        task = f"Engineering task #{number}: {issue['title']}\n{issue.get('body') or ''}\nCall both specialist agents and prepare a reviewed response."
        report = Runner.run_sync(tony, task, max_turns=12).final_output
        body = (
            "## Tony AI Engineering Review\n\n" + str(report)
            + "\n\n---\nAI-generated design proposal. No code was edited, "
              "tests run, or flight software deployed by this workflow."
        )
        github("POST", f"/repos/{REPO}/issues/{number}/comments",
               json={"body": body[:60000]})
        github("POST", f"/repos/{REPO}/issues/{number}/labels",
               json={"labels": ["tony-done"]})
        print(f"Processed {REPO}#{number}")
        break

if __name__ == "__main__":
    main()
