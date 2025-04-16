"""
JIRA Task Exporter - Extracts tasks from JIRA and exports them to CSV
"""

import requests
import csv
import re
import json
import urllib3
import os
from dotenv import load_dotenv
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

@dataclass
class JiraConfig:
    url: str
    username: str
    password: str
    verify_ssl: bool = False


class TextCleaner:
    @staticmethod
    def clean_field(field: Union[str, List, None]) -> str:
        pattern = r"\s\(IM-\d+\)"

        if not field:
            return ""

        if isinstance(field, list):
            cleaned_list = [re.sub(pattern, '', str(x)) for x in field]
            return ','.join(cleaned_list)

        return re.sub(pattern, '', str(field))


class JiraClient:
    def __init__(self, config: JiraConfig):

        self.config = config
        self.headers = {"Content-Type": "application/json"}
        self.auth = (config.username, config.password)

    def get_tasks(self, jql_query: str, max_results_per_page: int = 50) -> List[Dict[str, Any]]:
        start_at = 0
        all_tasks = []

        while True:
            params = {
                "jql": jql_query,
                "startAt": start_at,
                "maxResults": max_results_per_page
            }

            try:
                response = requests.get(
                    self.config.url,
                    headers=self.headers,
                    params=params,
                    auth=self.auth,
                    verify=self.config.verify_ssl
                )
                response.raise_for_status()

                issues = response.json().get("issues", [])
                all_tasks.extend(issues)

                if len(issues) < max_results_per_page:
                    break

                start_at += max_results_per_page

            except requests.exceptions.RequestException as err:
                print(f"Error occurred while fetching data from Jira: {err}")
                break

        return all_tasks


class JiraTaskFormatter:
    def __init__(self, cleaner: TextCleaner):

        self.cleaner = cleaner

    def get_nested_value(self, data: Dict[str, Any], key: str,
                         subkey: Optional[str] = None) -> str:
        if key not in data:
            return ""

        value = data[key]

        if not value:
            return ""

        if not subkey:
            return value

        if isinstance(value, dict) and subkey in value:
            return value[subkey] or ""

        return ""

    def format_task(self, task: Dict[str, Any]) -> Dict[str, str]:
        fields = task["fields"]

        l2_assignee = ([x.get("emailAddress", "") for x in fields.get("customfield_20145", [])]
                       if fields.get("customfield_20145") else [])

        responsible_team = self.cleaner.clean_field(fields.get("customfield_20161", ""))
        incident_type = self.get_nested_value(fields, "customfield_20163", "value")

        vendor_related = ""
        if "customfield_20906" in fields and fields["customfield_20906"]:
            vendor_related = fields["customfield_20906"].get("value", "")

        system_owner = ""
        if fields.get("customfield_20157") and "displayName" in fields["customfield_20157"]:
            system_owner = fields["customfield_20157"]["displayName"]

        return {
            "key": task["key"],
            "summary": fields.get("summary", ""),
            "reporter": fields.get("reporter", {}).get("displayName", ""),
            "L2 Assignee": ", ".join(l2_assignee),
            "Responsible Team": responsible_team,
            "Incident Detected type": incident_type,
            "Vendor Related Incidents": vendor_related,
            "status": fields.get("status", {}).get("name", ""),
            "priority": fields.get("priority", {}).get("name", ""),
            "System for incident": self.cleaner.clean_field(fields.get("customfield_20800", "")),
            "System Owner": system_owner,
            "System owner department": self.cleaner.clean_field(fields.get("customfield_20129", "")),
            "Impacted Business Process": self.cleaner.clean_field(fields.get("customfield_20160", "")),
            "Impacted Systems": self.cleaner.clean_field(fields.get("customfield_20164", "")),
            "Incident detected date": fields.get("customfield_20162", ""),
            "Incident start date": fields.get("customfield_20158", ""),
            "Incident end date": fields.get("customfield_20159", ""),
            "Incident Duration": self.get_nested_value(fields, "customfield_20908", "value"),
            "Downtime Type": self.get_nested_value(fields, "customfield_20901", "value"),
            "Downtime Outage": self.get_nested_value(fields, "customfield_20902", "value"),
            "Incident Details": fields.get("customfield_20136", ""),
            "Mitigation & Resolution": fields.get("customfield_20138", ""),
            "Root Cause Analysis": fields.get("customfield_20137", ""),
            "Corrective Actions": fields.get("customfield_20148", ""),
            "Incident solution": fields.get("customfield_20113", ""),
            "Real downtime duration": fields.get("customfield_21519", ""),
            "Error Rate": str(fields.get("customfield_20904", 0) or 0),
            "Problem Links": (json.dumps(fields["customfield_22301"]["value"])
                              if "customfield_22301" in fields
                                 and fields["customfield_22301"]
                                 and "value" in fields["customfield_22301"] else "")
        }


class DataExporter(ABC):
    @abstractmethod
    def export(self, data: List[Dict[str, Any]]) -> None:
        pass


class CSVExporter(DataExporter):

    def __init__(self, filename: str, delimiter: str = ';'):
        self.filename = filename
        self.delimiter = delimiter

        self.fieldnames = [
            "key", "summary", "reporter", "L2 Assignee", "Responsible Team",
            "Incident Detected type", "Vendor Related Incidents", "status", "priority",
            "System for incident", "System Owner", "System owner department",
            "Impacted Business Process", "Impacted Systems", "Incident detected date",
            "Incident start date", "Incident end date", "Downtime Type", "Downtime Outage",
            "Incident Duration", "Incident Details", "Root Cause Analysis",
            "Mitigation & Resolution", "Corrective Actions", "Incident solution",
            "Real downtime duration", "Error Rate", "Problem Links"
        ]

    def export(self, data: List[Dict[str, Any]]) -> None:
        try:
            with open(self.filename, mode="w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=self.fieldnames,
                    delimiter=self.delimiter
                )
                writer.writeheader()
                writer.writerows(data)

            print(f"Tasks exported to '{self.filename}' successfully.")
        except Exception as e:
            print(f"Error exporting to CSV: {e}")


class JiraTaskExporter:
    def __init__(self,
                 jira_client: JiraClient,
                 formatter: JiraTaskFormatter,
                 exporter: DataExporter):
        self.jira_client = jira_client
        self.formatter = formatter
        self.exporter = exporter

    def export_tasks(self, jql_query: str) -> None:
        tasks = self.jira_client.get_tasks(jql_query)

        if not tasks:
            print("No tasks found for the given query.")
            return

        formatted_tasks = [self.formatter.format_task(task) for task in tasks]

        self.exporter.export(formatted_tasks)


def main():
    jira_config = JiraConfig(
        url=os.getenv("JIRA_URL"),
        username=os.getenv("JIRA_USERNAME"),
        password=os.getenv("JIRA_PASSWORD")
    )

    cleaner = TextCleaner()
    jira_client = JiraClient(jira_config)
    formatter = JiraTaskFormatter(cleaner)
    exporter = CSVExporter("jira_exported_tasks.csv")
    task_exporter = JiraTaskExporter(jira_client, formatter, exporter)
    jql_query = os.getenv("JIRA_JQL", 'project = "DefaultProject"')
    task_exporter.export_tasks(jql_query)



if __name__ == "__main__":
    main()