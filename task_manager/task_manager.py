"""
    Prosty task manager z chatem
    
"""

from __future__ import annotations
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, List, Tuple, Dict, Any
import shlex
import json
from dotenv import load_dotenv

import psycopg
from psycopg.rows import dict_row

load_dotenv()

DATE_FORMATS = [
"%Y-%m-%d %H:%M",
"%Y-%m-%d",
"%Y/%m/%d %H:%M",
"%Y/%m/%d",
"%d.%m.%Y %H:%M",
"%d.%m.%Y",
]

class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3

class TaskStatus(str, Enum):
    TODO = 'todo'
    IN_PROGRESS = 'in_progress'
    DONE = 'done'

def parse_when(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    t = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(t,fmt)
        except ValueError:
            continue
    raise ValueError(f"Niepoprawny format daty/czasu: '{text}'")

def connect(db_url: Optional[str] = None) -> psycopg.Connection:
    url = db_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Brak DATABASE_URL. Ustaw zmienną w pliku .env")
    return psycopg.connect(url, autocommit=False, row_factory=dict_row)

def init_db(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
                CREATE TABLE IF NOT EXISTS tasks (
                id BIGSERIAL PRIMARY KEY,
                parent_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                due_at TIMESTAMP,
                estimate_min INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 2 CHECK (priority IN (1,2,3)),
                status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','in_progress','done')),
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
                );
                """
            )
    conn.commit()
    
def now_dt() -> datetime:
    return datetime.now().replace(microsecond=0)

@dataclass
class Task:
    id: int
    parent_id: Optional[int]
    title: str
    description: str
    due_at: Optional[datetime]
    estimate_min: int
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_row(cls, r: dict) -> "Task":
        return cls(
            id=r["id"],
            parent_id=r["parent_id"],
            title=r["title"],
            description=r["description"],
            due_at=r["due_at"],
            estimate_min=r["estimate_min"],
            priority=TaskPriority(r["priority"]),
            status=TaskStatus(r["status"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )


# CRUD

#Create

def add_task(conn, title, description="", due_at=None, estimate_min=0, priority=TaskPriority.NORMAL, parent_id=None) -> int:
    ts = now_dt()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tasks(parent_id,title,description,due_at,estimate_min,priority,status,created_at,updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (parent_id, title, description, due_at, estimate_min, priority.value, TaskStatus.TODO.value, ts, ts)
        )
        new_id = cur.fetchone()["id"]
    conn.commit()
    return new_id

#Update

def update_task(conn, task_id: int, **fields):
    if not fields:
        return
    allowed = {"title", "description", "due_at", "estimate_min", "priority", "status", "parent_id"}
    
    sets = []
    vals = []
    
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"Nieznane pole {k}")
        
        if k == "priority" and v is not None:
            vals.append(TaskPriority(v).value)
        elif k == "status" and v is not None:
            vals.append(TaskStatus(v).value)
        else:
            vals.append(v)
        sets.append(f"{k}=%s")
        
    sets.append("updated_at=%s")
    vals.extend([now_dt(), task_id])
    
    q = f"UPDATE tasks SET {','.join(sets)} WHERE id=%s"
    with conn.cursor() as cur:
        cur.execute(q, vals)
    conn.commit()

#Delete
def delete_task(conn,task_id:int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM tasks WHERE id=%s",(task_id,))
    conn.commit()
    
#Read
def get_task(conn, task_id: int) -> Task:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM tasks WHERE id=%s",(task_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Brak zadania {task_id}")
    return Task.from_row(row)

def list_tasks(conn,parent_id:Optional[int]=None)->List[Task]:
    query = "SELECT * FROM tasks WHERE parent_id "
    params = [parent_id]
    if parent_id is None:
        query += "IS NULL "
        params = []
    else:
        query += "=%s "
    query += "ORDER BY priority DESC, due_at ASC NULLS LAST"
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [Task.from_row(r) for r in rows]


# function call

def chat_call(payload: Dict[str, Any], db_url: Optional[str] = None) -> Dict[str, Any]:
    """Obsługa menedżera zadań przez payload JSON."""
    
    def handle_add(conn, p):
        due = parse_when(p.get("due_at"))
        priority = TaskPriority(p.get("priority", TaskPriority.NORMAL))
        new_id = add_task(conn,
                          title=p["title"],
                          description=p.get("description", ""),
                          due_at=due,
                          estimate_min=p.get("estimate_min", 0),
                          priority=priority,
                          parent_id=p.get("parent_id"))
        return {"status": "ok", "id": new_id}

    def handle_update(conn, p):
        fields = p.get("fields", {})
        if 'due_at' in fields:
            fields['due_at'] = parse_when(fields['due_at'])
        update_task(conn, p["id"], **fields)
        return {"status": "ok"}

    def handle_delete(conn, p):
        delete_task(conn, p["id"])
        return {"status": "ok"}

    def handle_show(conn, p):
        task = get_task(conn, p["id"])
        return {"status": "ok", "task": asdict(task)}

    def handle_list(conn, p):
        tasks = list_tasks(conn, p.get("parent_id"))
        return {"status": "ok", "tasks": [asdict(t) for t in tasks]}

    commands = {
        "add": handle_add,
        "update": handle_update,
        "delete": handle_delete,
        "show": handle_show,
        "list": handle_list,
    }

    cmd = payload.get("command")
    if cmd not in commands:
        return {"status": "error", "error": "Nieznana komenda"}

    try:
        with connect(db_url) as conn:
            init_db(conn)
            return commands[cmd](conn, payload)
    except (ValueError, KeyError, psycopg.Error) as e:
        return {"status": "error", "error": str(e)}
        

# chat tekstowy

def parse_args(args: List[str]) -> Dict[str, Any]:
    """Parsuje argumenty w stylu key:value lub key='value'."""
    params = {}
    for arg in args:
        if ':' not in arg:
            continue
        key, value = arg.split(':', 1)
        # Proste parsowanie typów
        if value.isdigit():
            params[key] = int(value)
        elif value.lower() in ['true', 'false']:
            params[key] = value.lower() == 'true'
        else:
            params[key] = value.strip("'\"")
    return params

def format_task(task: Dict[str, Any], indent: str = "") -> str:
    """Formatuje zadanie do czytelnego stringa."""
    due = task.get('due_at') or "brak"
    prio = TaskPriority(task['priority']).name
    desc = f" - {task['description']}" if task['description'] else ""
    return (
        f"{indent}[{task['id']}] {task['title']} ({task['status']})\n"
        f"{indent}  Prio: {prio}, Termin: {due}, Est: {task['estimate_min']}min{desc}"
    )

def main_chat():
    """Główna pętla czatu tekstowego."""
    print("Witaj w Menedżerze Zadań!")
    print("Dostępne komendy: add, list, show, update, delete, help, exit")
    print("Przykład: add title:'Nowe zadanie' description:'Opis' priority:3 due_at:'2024-12-31'")
    
    while True:
        try:
            line = input("> ").strip()
            if not line:
                continue
            if line in ["exit", "quit"]:
                break
            if line == "help":
                print("Przykłady:")
                print("  add title:'Zrobić zakupy' description:'Mleko, chleb' priority:3")
                print("  list")
                print("  list parent_id:1")
                print("  show id:1")
                print("  update id:1 status:done")
                print("  delete id:1")
                continue

            parts = shlex.split(line)
            command = parts[0]
            args = parse_args(parts[1:])
            
            payload = {"command": command}
            
            # Specjalna obsługa dla 'update'
            if command == 'update':
                if 'id' not in args:
                    raise ValueError("Brak 'id' dla komendy update")
                payload['id'] = args.pop('id')
                payload['fields'] = args
            else:
                payload.update(args)

            result = chat_call(payload)

            if result.get("status") == "error":
                print(f"Błąd: {result.get('error')}")
            else:
                print("OK")
                if command == 'add':
                    print(f"Dodano zadanie o ID: {result['id']}")
                elif command == 'show':
                    print(format_task(result['task']))
                elif command == 'list':
                    tasks = result.get('tasks', [])
                    if not tasks:
                        print("Brak zadań do wyświetlenia.")
                    for task in tasks:
                        print(format_task(task))
                        # Proste wyświetlanie podzadań
                        sub_tasks_payload = {"command": "list", "parent_id": task['id']}
                        sub_result = chat_call(sub_tasks_payload)
                        if sub_result.get('status') == 'ok':
                            for sub_task in sub_result.get('tasks', []):
                                print(format_task(sub_task, indent="  -> "))

        except (KeyboardInterrupt, EOFError):
            print("\nDo widzenia!")
            break
        except Exception as e:
            print(f"Wystąpił nieoczekiwany błąd: {e}")

if __name__ == "__main__":

    if not os.getenv("DATABASE_URL") or "user:password" in os.getenv("DATABASE_URL", ""):
        print("UWAGA: Zmienna DATABASE_URL nie jest poprawnie ustawiona w pliku .env.")
        print("Proszę, zaktualizuj plik .env o prawidłowe dane dostępowe do bazy danych.")
    else:
        main_chat()
