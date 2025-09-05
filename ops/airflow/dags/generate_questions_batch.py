# -*- coding: utf-8 -*-
# Airflow DAG to trigger agent service batch question generation

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Any, Dict, List

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator
import requests

AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://agent:8000")


def _chunk(lst: List[Any], size: int) -> List[List[Any]]:
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def build_specs(conf: Dict[str, Any]) -> List[Dict[str, Any]]:
    subject = conf.get("subject")
    topic = conf.get("topic")
    total_questions = int(conf.get("total_questions", 50))
    difficulty = conf.get("difficulty", "medium")
    class_level = conf.get("class_level")
    skills = conf.get("skills", [])
    question_type = conf.get("question_type", "multiple_choice")

    specs = []
    for _ in range(total_questions):
        specs.append(
            {
                "subject": subject,
                "topic": topic,
                "difficulty": difficulty,
                "class_level": class_level,
                "skills": skills,
                "question_type": question_type,
            }
        )
    return specs


def call_agent_batch(specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    url = f"{AGENT_BASE_URL}/admin/generate/batch/v2"
    resp = requests.post(url, json=specs, timeout=300)
    resp.raise_for_status()
    return resp.json()


def run(conf: Dict[str, Any], ti=None, **_):
    concurrency = max(1, min(int(conf.get("concurrency", 10)), 64))

    specs = build_specs(conf)
    # Ensure batch size respects agent batch limit (5)
    batch_size = max(1, min(5, math.ceil(len(specs) / concurrency)))
    chunks = _chunk(specs, batch_size)

    results: List[Dict[str, Any]] = []
    for chunk in chunks:
        data = call_agent_batch(chunk)
        # Ensure list
        if isinstance(data, list):
            results.extend(data)
        else:
            results.append(data)

    # Optionally store XCom summary
    if ti is not None:
        ti.xcom_push(key="results_count", value=len(results))


def make_task(dag: DAG) -> PythonOperator:
    return PythonOperator(
        task_id="generate_questions",
        python_callable=run,
        op_kwargs={"conf": "{{ dag_run.conf or {} }}"},
        provide_context=True,
    )


def parse_conf(conf_raw: Any) -> Dict[str, Any]:
    if isinstance(conf_raw, dict):
        return conf_raw
    try:
        return json.loads(conf_raw) if conf_raw else {}
    except Exception:
        return {}


def entrypoint(**context):
    conf = parse_conf(context.get("dag_run").conf)
    ti = context.get("ti")
    return run(conf=conf, ti=ti)


def create_dag() -> DAG:
    with DAG(
        dag_id="generate_questions_batch",
        description="Batch generation of subject/topic questions via agent service",
        start_date=datetime(2024, 1, 1),
        schedule_interval=None,
        catchup=False,
        params={
            "subject": Param("mathematics", type="string"),
            "topic": Param(None, type=["null", "string"]),
            "total_questions": Param(50, type="integer"),
            "difficulty": Param("medium", enum=["easy", "medium", "hard", "adaptive"]),
            "class_level": Param(None, type=["null", "string"]),
            "skills": Param([], type="array"),
            "question_type": Param("multiple_choice", enum=["multiple_choice", "short_answer", "true_false", "problem_solving"]),
            "concurrency": Param(10, type="integer"),
        },
        tags=["generation", "agent", "questions"],
    ) as dag:
        generate = PythonOperator(
            task_id="generate",
            python_callable=entrypoint,
            provide_context=True,
        )

        generate
    return dag


globals()["generate_questions_batch"] = create_dag()
