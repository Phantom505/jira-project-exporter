# Jira Project Exporter

A Python script that exports tasks from a Jira project to a CSV file using a JQL query.  
It connects to Jira via its REST API and formats the task data into a clean CSV export.

## 🚀 Features

- Fetch tasks using a JQL query
- Clean and transform Jira fields (including custom fields)
- Export to CSV with semicolon delimiter
- Simple and extensible architecture

## ⚙️ Configuration

Set your Jira configuration in .env:

```python
JIRA_URL=https://your-jira-domain.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_PASSWORD=your-api-token
JIRA_JQL=project = "IT Incident Management"
