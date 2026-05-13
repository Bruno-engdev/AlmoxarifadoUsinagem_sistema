"""
Seed mensal: gera 120 movimentacoes por mes (Jan-mes atual de 2026)
e atualiza os precos unitarios de todas as ferramentas (R$30-R$80).

Uso:
    python seed_monthly.py
"""

import random
from calendar import monthrange
from datetime import datetime

from app.database import SessionLocal
from app.models import Employee, Machine, Movement, Tool

MOVEMENTS_PER_MONTH = 120
UNIT_COST_MIN = 30.0
UNIT_COST_MAX = 80.0
START_YEAR = 2026
START_MONTH = 1


def update_tool_prices(db):
    tools = db.query(Tool).all()
    for tool in tools:
        tool.unit_cost = round(random.uniform(UNIT_COST_MIN, UNIT_COST_MAX), 2)
    db.commit()
    print(f"  {len(tools)} ferramentas com precos atualizados (R${UNIT_COST_MIN:.0f}-R${UNIT_COST_MAX:.0f}).")
    return tools


def seed_month(db, tools, employees, machines, year, month):
    _, last_day = monthrange(year, month)
    generated = 0

    for _ in range(MOVEMENTS_PER_MONTH):
        tool = random.choice(tools)
        movement_type = random.choice(["IN", "OUT"])
        quantity = random.randint(1, 3)

        timestamp = datetime(
            year, month,
            random.randint(1, last_day),
            random.randint(6, 17),
            random.randint(0, 59),
        )

        employee = None
        machine = None
        loan_status = None

        if movement_type == "OUT":
            category = "EMPRESTIMO"
            employee = random.choice(employees)
            loan_status = random.choice(["PENDENTE", "ENTREGUE"])
            if tool.current_stock < quantity:
                tool.current_stock = quantity
            tool.current_stock -= quantity
        else:
            category = "REPOSICAO"
            machine = random.choice(machines)
            tool.current_stock += quantity

        db.add(Movement(
            tool_id=tool.id,
            employee_id=employee.id if employee else None,
            machine_id=machine.id if machine else None,
            movement_type=movement_type,
            category=category,
            quantity=quantity,
            unit_cost=tool.unit_cost,
            timestamp=timestamp,
            loan_status=loan_status,
            notes=f"Seed {year}/{month:02d}",
        ))
        generated += 1

    db.commit()
    print(f"  {year}/{month:02d} -> {generated} movimentacoes inseridas.")


def main():
    db = SessionLocal()
    try:
        tools     = db.query(Tool).all()
        employees = db.query(Employee).all()
        machines  = db.query(Machine).all()

        if not tools:
            print("Nenhuma ferramenta encontrada. Execute seed_data.py primeiro.")
            return
        if not employees:
            print("Nenhum funcionario encontrado. Execute seed_data.py primeiro.")
            return
        if not machines:
            print("Nenhuma maquina encontrada. Execute seed_data.py primeiro.")
            return

        print("Atualizando precos unitarios das ferramentas...")
        tools = update_tool_prices(db)

        now = datetime.now()
        print(f"\nGerando {MOVEMENTS_PER_MONTH} movimentacoes/mes "
              f"de {START_YEAR}/{START_MONTH:02d} ate {now.year}/{now.month:02d}...\n")

        year, month = START_YEAR, START_MONTH
        while (year, month) <= (now.year, now.month):
            seed_month(db, tools, employees, machines, year, month)
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

        print("\nConcluido.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
