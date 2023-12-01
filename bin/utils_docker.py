import docker


def export_container_info():
    """
    Export information about all containers.

    Returns:
        A list of dictionaries containing information about each container.
    """
    client = docker.from_env()
    containers = client.containers.list(all=True)

    container_info = []
    for container in containers:
        info = {
            "id": container.id,
            "name": container.name,
            "image": container.image.tags[0],
            "status": container.status,
            "created": container.attrs["Created"],
            "restart_policy": container.attrs["HostConfig"]["RestartPolicy"]["Name"],
            "last_start": container.attrs["State"]["StartedAt"],
        }
        container_info.append(info)

    return container_info


def start_container(container_id):
    client = docker.from_env()
    container = client.containers.get(container_id)
    container.start()


def stop_container(container_id):
    client = docker.from_env()
    container = client.containers.get(container_id)
    container.stop()


def restart_container(container_id):
    client = docker.from_env()
    container = client.containers.get(container_id)
    container.restart()


def get_container_logs(container_id, tail=100):
    """
    Get the tail of a container's logs.

    Args:
        container_id (str): The ID of the container.
        tail (int): The number of lines to retrieve from the end of the logs. Default is 100.

    Returns:
        str: The tail of the container's logs.
    """
    client = docker.from_env()
    container = client.containers.get(container_id)
    logs = container.logs(tail=tail).decode("utf-8")
    return logs

