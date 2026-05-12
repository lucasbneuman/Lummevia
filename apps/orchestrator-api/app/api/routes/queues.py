from fastapi import APIRouter, HTTPException, status

from lummevia_queue import TaskQueue, TaskQueueItem, TaskQueueRegistry


router = APIRouter(prefix="/queues", tags=["queues"])


@router.get("", response_model=list[TaskQueue])
def list_queues() -> list[TaskQueue]:
    return TaskQueueRegistry.default().list_queues()


@router.get("/{queue_id}", response_model=TaskQueue)
def get_queue(queue_id: str) -> TaskQueue:
    queue = TaskQueueRegistry.default().get_queue(queue_id)
    if queue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task queue '{queue_id}' not found.",
        )
    return queue


@router.get("/{queue_id}/ready", response_model=list[TaskQueueItem])
def list_ready_items(queue_id: str) -> list[TaskQueueItem]:
    queue = TaskQueueRegistry.default().get_queue(queue_id)
    if queue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task queue '{queue_id}' not found.",
        )
    return TaskQueueRegistry.default().list_ready_items(queue_id)
