"""
Тест для демонстрации ПРОБЛЕМЫ race condition.

Этот тест должен ПРОХОДИТЬ, подтверждая, что при использовании
pay_order_unsafe() возникает двойная оплата.
"""

import asyncpg
import asyncio
import pytest
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.application.payment_service import PaymentService


# TODO: Настроить подключение к тестовой БД
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace"


@pytest.fixture
async def db_session():
    """
    Создать сессию БД для тестов.
    
    TODO: Реализовать фикстуру:
    1. Создать engine
    2. Создать session maker
    3. Открыть сессию
    4. Yield сессию
    5. Закрыть сессию после теста
    """
    engine = create_async_engine(DATABASE_URL)
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()

    # TODO: Реализовать создание сессии
    #raise NotImplementedError("TODO: Реализовать db_session fixture")


@pytest.fixture
async def test_order(db_session):
    """
    Создать тестовый заказ со статусом 'created'.
    
    TODO: Реализовать фикстуру:
    1. Создать тестового пользователя
    2. Создать тестовый заказ со статусом 'created'
    3. Записать начальный статус в историю
    4. Вернуть order_id
    5. После теста - очистить данные
    """
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO users (id, email, name) VALUES (:id, :email, :name)"),
        {'id': str(user_id), 'email': f'null_{user_id}@test.com', 'name': 'Test User'}
    )
    await db_session.execute(
        text("INSERT INTO orders (id, user_id, status, total_amount) VALUES (:id, :user_id, 'created', 100.0)"),
        {'id': str(order_id), 'user_id': str(user_id)}
    )
    await db_session.commit()
    yield order_id 

    await db_session.execute(text("DELETE FROM order_status_history WHERE order_id = :id"), {'id': str(order_id)})
    await db_session.execute(text("DELETE FROM orders WHERE id = :id"), {'id': str(order_id)})
    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {'id': str(user_id)})
    await db_session.commit()
    # TODO: Реализовать создание тестового заказа
    #raise NotImplementedError("TODO: Реализовать test_order fixture")


@pytest.mark.asyncio
async def test_concurrent_payment_unsafe_demonstrates_race_condition(db_session, test_order):
    """
    Тест демонстрирует проблему race condition при использовании pay_order_unsafe().
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: Тест ПРОХОДИТ, подтверждая, что заказ был оплачен дважды.
    Это показывает, что метод pay_order_unsafe() НЕ защищен от конкурентных запросов.
    
    TODO: Реализовать тест следующим образом:
    
    1. Создать два экземпляра PaymentService с РАЗНЫМИ сессиями
       (это имитирует два независимых HTTP-запроса)
       
    2. Запустить два параллельных вызова pay_order_unsafe():
       
       async def payment_attempt_1():
           service1 = PaymentService(session1)
           return await service1.pay_order_unsafe(order_id)
           
       async def payment_attempt_2():
           service2 = PaymentService(session2)
           return await service2.pay_order_unsafe(order_id)
           
       results = await asyncio.gather(
           payment_attempt_1(),
           payment_attempt_2(),
           return_exceptions=True
       )
       
    3. Проверить историю оплат:
       
       service = PaymentService(session)
       history = await service.get_payment_history(order_id)
       
       # ОЖИДАЕМ ДВЕ ЗАПИСИ 'paid' - это и есть проблема!
       assert len(history) == 2, "Ожидалось 2 записи об оплате (RACE CONDITION!)"
       
    4. Вывести информацию о проблеме:
       
       print(f"⚠️ RACE CONDITION DETECTED!")
       print(f"Order {order_id} was paid TWICE:")
       for record in history:
           print(f"  - {record['changed_at']}: status = {record['status']}")
    """
    order_id = test_order
    engine = create_async_engine(DATABASE_URL)

    async def payment_attempt_1():
        async with AsyncSession(engine) as session1:
            service1 = PaymentService(session1)
            return await service1.pay_order_unsafe(order_id)

    async def payment_attempt_2():
        async with AsyncSession(engine) as session2:
            service2 = PaymentService(session2)
            return await service2.pay_order_unsafe(order_id)

    results = await asyncio.gather(
        payment_attempt_1(),
        payment_attempt_2(),
        return_exceptions=True
    )
    await engine.dispose()

    history = await PaymentService(db_session).get_payment_history(order_id)
    assert len(history) == 2, f"Ожидалось 2 записи (RACE CONDITION!), получено {len(history)}"

    print(f"⚠️ RACE CONDITION DETECTED!")
    print(f"Order {order_id} was paid TWICE:")
    for record in history:
        print(f"  - {record['changed_at']}: status = {record['status']}")

    # TODO: Реализовать тест, демонстрирующий race condition
    #raise NotImplementedError("TODO: Реализовать test_concurrent_payment_unsafe")


@pytest.mark.asyncio
async def test_concurrent_payment_unsafe_both_succeed():
    """
    Дополнительный тест: проверить, что ОБЕ транзакции успешно завершились.
    
    TODO: Реализовать проверку, что:
    1. Обе попытки оплаты вернули успешный результат
    2. Ни одна не выбросила исключение
    3. Обе записали в историю
    
    Это подтверждает, что проблема не в ошибках, а в race condition.
    """
    engine = create_async_engine(DATABASE_URL)
    user_id = uuid.uuid4()
    order_id = uuid.uuid4()

    async with AsyncSession(engine) as session:
        await session.execute(
            text("INSERT INTO users (id, email, name) VALUES (:id, :email, :name)"),
            {'id': str(user_id), 'email': f'null_{user_id}@test.com', 'name': 'Test'}
        )
        await session.execute(
            text("INSERT INTO orders (id, user_id, status, total_amount) VALUES (:id, :user_id, 'created', 100.0)"),
            {'id': str(order_id), 'user_id': str(user_id)}
        )
        await session.commit()
    async def payment_attempt_1():
        async with AsyncSession(engine) as session1:
            res = await session1.execute(
                text("SELECT status FROM orders WHERE id = :order_id"),
                {'order_id': str(order_id)}
            )
            status = res.scalar()
            if status != 'created':
                from app.domain.exceptions import OrderAlreadyPaidError
                raise OrderAlreadyPaidError(order_id)
            # Пауза ПОСЛЕ чтения — сессия 2 успевает прочитать то же значение
            await asyncio.sleep(0.3)
            await session1.execute(
                text("UPDATE orders SET status = 'paid' WHERE id = :order_id AND status = 'created'"),
                {'order_id': str(order_id)}
            )
            await session1.execute(
                text("INSERT INTO order_status_history (id, order_id, status, changed_at) VALUES (gen_random_uuid(), :order_id, 'paid', NOW())"),
                {'order_id': str(order_id)}
            )
            await session1.commit()
            return {'order_id': str(order_id), 'status': 'paid'}

    async def payment_attempt_2():
        async with AsyncSession(engine) as session2:
            return await PaymentService(session2).pay_order_unsafe(order_id)

    results = await asyncio.gather(
        payment_attempt_1(),
        payment_attempt_2(),
        return_exceptions=True
    )
    success_count = sum(1 for r in results if not isinstance(r, Exception))
    assert success_count == 2, f"кол-во успехов {success_count} (ожидалось 2 — обе транзакции должны пройти, демонстрируя двойную оплату)"
    async with AsyncSession(engine) as session:
        await session.execute(text("DELETE FROM order_status_history WHERE order_id = :id"), {'id': str(order_id)})
        await session.execute(text("DELETE FROM orders WHERE id = :id"), {'id': str(order_id)})
        await session.execute(text("DELETE FROM users WHERE id = :id"), {'id': str(user_id)})
        await session.commit()
    await engine.dispose()
    # TODO: Реализовать проверку успешности обеих транзакций
    #raise NotImplementedError("TODO: Реализовать test_concurrent_payment_unsafe_both_succeed")


if __name__ == "__main__":
    """
    Запуск теста:
    
    cd backend
    export PYTHONPATH=$(pwd)
    pytest app/tests/test_concurrent_payment_unsafe.py -v -s
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
    ✅ test_concurrent_payment_unsafe_demonstrates_race_condition PASSED
    
    Вывод должен показывать:
    ⚠️ RACE CONDITION DETECTED!
    Order XXX was paid TWICE:
      - 2024-XX-XX: status = paid
      - 2024-XX-XX: status = paid
    """
    pytest.main([__file__, "-v", "-s"])
