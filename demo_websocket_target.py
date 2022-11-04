#!/usr/bin/env python
# https://websockets.readthedocs.io/en/stable/howto/quickstart.html , including wss

from time import sleep, time
import random
import itertools
import threading

import json
import asyncio
import websockets
import socket

# for const
from typing import Final

# consts
wsLraMsgRequestType: Final[list[str]] = [
    "regAllRequire",
    "regDrvRequire",
    "regAdxlRequire",
    "dataRTNewestRequire",
    "dataRTKeepRequire",
    "dataRTStopRequire",
    "moduleInfoRequire",
]

wsLraMsgUpdateType: Final[list[str]] = [
    "webInfoUpdate",
    "regAllUpdate",
    "regDrvUpdate",
    "regAdxlUpdate",
    "drvCmdUpdate",
]

wsLraMsgResponseType: Final[list[str]] = [
    "regAllRequireResponse",
    "regDrvRequireResponse",
    "regAdxlRequireResponse",
    "dataRTNewestRequireResponse",
    "dataRTKeepRequireResponse",
    "dataRTStopRequireResponse",
    "moduleInfoRequireResponse",
]

wsLraMsgReceiveType: Final[list[str]] = [
    "webInfoUpdateRecv",
    "regAllUpdateRecv",
    "regDrvUpdateRecv",
    "regAdxlUpdateRecv",
    "drvCmdUpdateRecv",
]

# TODO: add to vue
wsLraMachiningServerMsgRequestType: Final[list[str]] = [
    "serverInfoRequire",
    "drvCmdKeepRequire",
    "drvCmdStopRequire"
]

wsLraMachiningServerMsgResponseType: Final[list[str]] = [
    "serverInfoRequireResponse",
    "drvCmdKeepRequireResponse",
    "drvCmdStopRequireResponse"
]


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    # print(s.getsockname()[0])
    ip = s.getsockname()[0]
    s.close()
    return ip


class Module:
    id_obj = itertools.count()

    def __init__(self, uuid) -> None:
        self.name = "ModuleServer" + str(next(Module.id_obj))
        self.uuid = uuid  # if not empty -> change web side uuid(mid)
        self.keepSendingData = False

    async def rt_data_keep_send(self, websocket) -> None:
        # FIXME msg type incorrect
        while (self.keepSendingData):
            data = self.rt_data_generator()
            msg = {"type": "dataRTKeepRequireResponse",
                   "uuid": self.uuid, "data": data, "timestamp": time()}
            await websocket.send(json.dumps(msg))
            sleep(1)  # FIXME

    def rt_data_generator(self) -> str:
        return "send real time data"


class Server:
    id_obj = itertools.count()

    def __init__(self, uuid) -> None:
        self.uuid = uuid
        self.name = next(Server.id_obj)
        self.keepSendingData = False

    async def drv_cmd_publisher(self, websocket) -> None:
        while (self.keepSendingData):
            data = self.drvcmd_generator()
            msg = {"type": "drvCmdKeepRequireResponse",
                   "uuid": self.uuid, "data": data, "timestamp": time()}
            await websocket.send(json.dumps(msg))
            sleep(1)  # FIXME

    def drvcmd_generator():
        x, y, z = random.randint(0, 255), random.randint(
            0, 255), random.randint(0, 255)
        return {"x": x, "y": y, "z": z}


# global state
serverList = []
moduleList = []

# TODO: 可以化簡
# 避免先有其他 request， 統一處理未註冊狀態


def try_to_find_module(uuid) -> Module:
    global moduleList
    try:
        return next(x for x in moduleList if x.uuid == uuid)
    except StopIteration:
        module_candidate = Module(uuid)
        moduleList.append(module_candidate)
        return module_candidate


def try_to_find_server(uuid) -> Server:
    global serverList
    try:
        return next(x for x in serverList if x.uuid == uuid)
    except StopIteration:
        server_candidate = Server(uuid)
        serverList.append(server_candidate)
        return server_candidate


async def module_parse(websocket, message) -> str:
    global moduleList

    msg = json.loads(message)
    msg_rtn = {}

    test_value = ""

    # type determine

    msg_type = msg["type"]
    msg_rtn_type = ""

    if "Require" in msg_type:
        idx = wsLraMsgRequestType.index(
            msg_type) if msg_type in wsLraMsgRequestType else None
        msg_rtn_type = wsLraMsgResponseType[idx] if idx != None else "unknown"

    elif "Update" in msg_type:
        idx = wsLraMsgUpdateType.index(
            msg_type) if msg_type in wsLraMsgUpdateType else None
        msg_rtn_type = wsLraMsgReceiveType[idx] if idx != None else "unknown"
    else:
        msg_rtn_type = "unknown"

    target_uuid = msg["uuid"]

    msg_rtn["uuid"] = target_uuid
    msg_rtn["type"] = msg_rtn_type

    if msg["type"] == "regAllRequire":
        msg_rtn["data"] = {"regName": ["Reg1"], "regValue": [0x12]}

    elif msg["type"] == "moduleInfoRequire":
        module_candidate = try_to_find_module(target_uuid)

        if module_candidate is None:
            module_candidate = Module(target_uuid)
            moduleList.append(module_candidate)

        msg_rtn["data"] = {"name": module_candidate.name}

    # a lot of if ...

    elif msg["type"] == "dataRTKeepRequire":
        tmp_module = try_to_find_module(target_uuid)

        if tmp_module is not None and tmp_module.keepSendingData == False:
            tmp_module.keepSendingData = True
            threading.Thread(target=tmp_module.rt_data_keep_send(websocket))
            msg_rtn["data"] = "ok"

    elif msg["type"] == "dataRTStopRequire":
        tmp_module = try_to_find_module(target_uuid)

        if tmp_module is not None:
            tmp_module.keepSendingData = False
            msg_rtn["data"] = "ok"

    # TODO: onclose -> remove Module from list (simulator only)
    else:
        print("get msg unknown type: ", msg)

    msg_rtn["timestamp"] = time()

    return json.dumps(msg_rtn)


async def server_parse(websocket, message) -> str:
    msg = json.loads(message)
    msg_rtn = {}

    msg_type = msg["type"]
    msg_rtn_type = ""

    if "Require" in msg_type:
        idx = wsLraMachiningServerMsgRequestType.index(
            msg_type) if msg_type in wsLraMachiningServerMsgRequestType else None
        msg_rtn_type = wsLraMachiningServerMsgResponseType[idx] if idx != None else "unknown"

    else:
        msg_rtn_type = "unknown"

    target_uuid = msg["uuid"]

    msg_rtn["uuid"] = target_uuid
    msg_rtn["type"] = msg_rtn_type

    if msg["type"] == "serverInfoRequire":
        server_candidate = try_to_find_server(target_uuid)
        msg_rtn["data"] = {"name": server_candidate.name}

    elif msg["type"] == "drvCmdKeepRequire":
        server = try_to_find_server(target_uuid)
        threading.Thread(target=server.drv_cmd_publisher(websocket=websocket))
        msg_rtn["data"] = "ok"

    elif msg["type"] == "drvCmdStopRequire":
        msg_rtn["data"] = "ok"

    msg_rtn["timestamp"] = time()

    return json.dumps(msg_rtn)


async def module_echo(websocket):
    async for message in websocket:
        # parse message
        msg_rtn = await module_parse(websocket, message)

        # debug only
        # print(message)

        # if echo server => enable
        await websocket.send(msg_rtn)


async def server_echo(websocket):
    async for message in websocket:
        msg_rtn = await server_parse(websocket, message)

        await websocket.send(msg_rtn)


async def run_on_port(port1, port2):
    module_server = await websockets.serve(module_echo, get_ip(), port1)
    print("module open on ip:", get_ip(), "at port:", port1)
    main_server = await websockets.serve(server_echo, get_ip(), port2)
    print("server open on ip:", get_ip(), "at port:", port2)
    await asyncio.gather(module_server.wait_closed(), main_server.wait_closed())
    # await asyncio.Future()  # run forever


asyncio.run(run_on_port(8764, 8765))
