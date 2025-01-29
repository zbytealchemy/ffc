import asyncio
from datetime import datetime, timedelta

import pytest
from ffc.agents.sample_agent import SampleAgent, TaskStatus


@pytest.fixture
async def mock_agent() -> SampleAgent:
    """Create a test agent."""
    agent = SampleAgent("TestAgent")
    await agent.initialize()
    yield agent
    await agent.stop()

async def sample_task(duration: float = 0.1) -> str:
    await asyncio.sleep(duration)
    return "completed"

async def failing_task() -> None:
    raise ValueError("Task failed")

@pytest.mark.asyncio
async def test_init() -> None:
    agent = SampleAgent("TestAgent")
    assert agent.name == "TestAgent"
    assert len(agent.tasks) == 0

@pytest.mark.asyncio
async def test_add_task(mock_agent: SampleAgent) -> None:
    async for agent in mock_agent:
        await agent.add_task("task1", sample_task)
        assert len(agent.tasks) == 1
        assert "task1" in agent.tasks
        assert agent.tasks["task1"].status == TaskStatus.PENDING

@pytest.mark.asyncio
async def test_process_tasks(mock_agent: SampleAgent) -> None:
    async for agent in mock_agent:
        await agent.add_task("task1", sample_task)
        await agent.process_tasks()
        assert agent.tasks["task1"].status == TaskStatus.COMPLETED

@pytest.mark.asyncio
async def test_get_status(mock_agent: SampleAgent) -> None:
    async for agent in mock_agent:
        await agent.add_task("task1", sample_task)
        status = agent.get_status()
        assert "pending: 1" in status.lower()
        
        await agent.process_tasks()
        status = agent.get_status()
        assert "completed: 1" in status.lower()

    agent = SampleAgent("TestAgent")
    await agent.add_task("task1", sample_task)
    initial_status = agent.get_status()
    assert "pending: 1" in initial_status.lower()
    
    await agent.process_tasks()
    final_status = agent.get_status()
    assert "completed: 1" in final_status.lower()

@pytest.mark.asyncio
async def test_task_dependencies(mock_agent: SampleAgent) -> None:
    async for agent in mock_agent:
        await agent.add_task("task1", sample_task, duration=0.1)
        await agent.add_task(
            "task2", 
            sample_task,
            duration=0.1,
            dependencies={"task1"}
        )
        await agent.process_tasks(max_concurrent=1)  

        assert agent.tasks["task1"].status == TaskStatus.COMPLETED
        assert agent.tasks["task2"].status == TaskStatus.COMPLETED

        await agent.add_task("task3", sample_task, duration=0.1)
        await agent.add_task("task4", sample_task, duration=0.1)
        await agent.add_task("task5", sample_task, duration=0.1)
        await agent.add_task(
            "task6", 
            sample_task,
            duration=0.1,
            dependencies={"task3", "task4"}
        )

        await agent.process_tasks(max_concurrent=1)  

        assert agent.tasks["task3"].status == TaskStatus.COMPLETED
        assert agent.tasks["task4"].status == TaskStatus.COMPLETED
        assert agent.tasks["task5"].status == TaskStatus.COMPLETED

@pytest.mark.asyncio
async def test_retry_mechanism(mock_agent: SampleAgent) -> None:
    async for agent in mock_agent:
        await agent.add_task(
            "failing_task",
            failing_task,
            max_retries=2,
            retry_delay=0.1
        )
    
        with pytest.raises(ValueError):
            await agent.process_tasks()

        task = agent.tasks["failing_task"]
        assert task.status == TaskStatus.FAILED
        assert task.retry_count == 2
        assert isinstance(task.error, ValueError)

@pytest.mark.asyncio
async def test_parallel_execution(mock_agent: SampleAgent) -> None:
    task_count = 3
    async for agent in mock_agent:
        for i in range(task_count):
            await agent.add_task(
                f"task{i}",
                sample_task,
                duration=0.1
            )
    
    start_time = datetime.now()
    async for agent in mock_agent:
        await agent.process_tasks(max_concurrent=task_count)
    end_time = datetime.now()
    
    execution_time = (end_time - start_time).total_seconds()
    assert execution_time < 0.3

    async for agent in mock_agent:
        for i in range(task_count):
            task = agent.tasks[f"task{i}"]
            assert task.status == TaskStatus.COMPLETED
            assert task.duration < timedelta(seconds=0.2)

    async for agent in mock_agent:
        completed_count = sum(
            1 for task in agent.tasks.values()
            if task.status == TaskStatus.COMPLETED
        )
        assert completed_count == task_count

    # execution_time = (end_time - start_time).total_seconds()
    # assert execution_time < 0.3
