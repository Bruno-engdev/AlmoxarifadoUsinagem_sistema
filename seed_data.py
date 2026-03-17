import random
from datetime import datetime, timedelta

from app.database import SessionLocal, init_db
from app.models import ToolType, Machine, Employee, Tool, Movement


def seed_tool_types(db):
    default_tool_types = [
        "Drill", "End Mill", "Insert", "Tap", "Reamer", "Indexable Insert"
    ]
    existing_names = {tool_type.name for tool_type in db.query(ToolType).all()}
    for name in default_tool_types:
        if name not in existing_names:
            db.add(ToolType(name=name))
    db.commit()
    print("ToolTypes checked.")
    return db.query(ToolType).all()


def seed_machines(db):
    machine_names = [
        "Fresadora 1", "Fresadora 2", "Fresadora 3",
        "Torno Convencional 1", "Torno Convencional 2", "Torno Convencional 3",
        "Eletroerosão a Fio", "Ajustagem", "Torno CNC 1", "Torno CNC 2",
        "Centro de Torneamento", "Centro de Usinagem 1", "Centro de Usinagem 2",
        "Centro de Usinagem 3", "Centro de Usinagem 4", "Portal",
    ]
    existing_names = {machine.name for machine in db.query(Machine).all()}
    for name in machine_names:
        if name not in existing_names:
            db.add(Machine(name=name))
    db.commit()
    print("Machines checked.")
    return db.query(Machine).all()


def seed_employees(db):
    employee_names = [
        "Carlos Silva", "Ana Souza", "Joao Pereira",
        "Mariana Lima", "Lucas Oliveira", "Fernanda Costa",
        "Rafael Gomes", "Beatriz Santos", "Pedro Almeida",
        "Camila Rocha",
    ]
    existing_names = {employee.name for employee in db.query(Employee).all()}
    for name in employee_names:
        if name not in existing_names:
            db.add(Employee(name=name, department="Usinagem"))
    db.commit()
    print("Employees checked.")
    return db.query(Employee).all()


def seed_tools(db, tool_types, machines):
    tool_names = [
        "Drill O6", "Drill O10", "End Mill 4mm", "End Mill 8mm",
        "Insert A", "Insert B", "Tap M6", "Tap M10", "Reamer 12mm",
        "Indexable Insert 20x20", "Drill O12", "End Mill 12mm",
        "Face Mill 50mm", "Insert C", "Broca Centro 5mm",
    ]
    existing_names = {tool.name for tool in db.query(Tool).all()}
    for name in tool_names:
        if name in existing_names:
            continue
        tool_type = random.choice(tool_types)
        machine = random.choice(machines)
        min_stock = random.randint(1, 5)
        max_stock = random.randint(min_stock + 3, min_stock + 15)
        current_stock = random.randint(0, max_stock)

        tool = Tool(
            name=name,
            description=f"Ferramenta ficticia {name} para {tool_type.name}",
            tool_type_id=tool_type.id,
            location=machine.name[:10],
            min_stock=min_stock,
            max_stock=max_stock,
            current_stock=current_stock,
            unit_cost=round(random.uniform(10, 500), 2),
            is_critical=random.choice([0, 1]),
            avg_lifespan_hours=round(random.uniform(20, 200), 1),
        )
        db.add(tool)

    db.commit()
    print("Tools checked.")
    return db.query(Tool).all()


def seed_movements(db, tools, employees, machines):
    target_count = 120
    current_count = db.query(Movement).count()
    if current_count >= target_count:
        print("Movements already at target volume.")
        return

    generated = 0
    for _ in range(target_count - current_count):
        tool = random.choice(tools)
        movement_type = random.choice(["IN", "OUT"])
        quantity = random.randint(1, 3)
        timestamp = datetime.now() - timedelta(days=random.randint(0, 90))

        employee = None
        machine = None
        category = random.choice(["EMPRESTIMO", "REPOSICAO"])
        loan_status = None

        if movement_type == "OUT":
            category = "EMPRESTIMO"
            employee = random.choice(employees)
            loan_status = "PENDENTE"
            if tool.current_stock < quantity:
                continue
            tool.current_stock -= quantity
        else:
            category = "REPOSICAO"
            machine = random.choice(machines)
            tool.current_stock += quantity

        movement = Movement(
            tool_id=tool.id,
            employee_id=employee.id if employee else None,
            machine_id=machine.id if machine else None,
            movement_type=movement_type,
            category=category,
            quantity=quantity,
            timestamp=timestamp,
            loan_status=loan_status,
            notes="Carga inicial para dashboard",
        )
        db.add(movement)
        generated += 1

    db.commit()
    print(f"{generated} movements seeded.")


def main():
    init_db()
    db = SessionLocal()
    try:
        tool_types = seed_tool_types(db)
        machines = seed_machines(db)
        employees = seed_employees(db)
        tools = seed_tools(db, tool_types, machines)
        seed_movements(db, tools, employees, machines)
        print("Database seeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()