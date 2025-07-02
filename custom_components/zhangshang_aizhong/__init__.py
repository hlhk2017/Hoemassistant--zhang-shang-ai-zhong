import logging
import aiohttp
import asyncio
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import discovery
from homeassistant.const import CONF_AUTHENTICATION, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

DOMAIN = "zhangshang_aizhong"
SCAN_INTERVAL = 3600  # 每小时更新一次数据
HOST = "yxxt2.aaapublic.com"
LOGIN_URL = f"https://{HOST}/api/app/login"
GET_CART_URL = f"https://{HOST}/api/cart/getCart"
QUERY_CUST_INFO_URL = f"https://{HOST}/api/app/queryCustInfo"
USER_SWITCH_HANDLER_URL = f"https://{HOST}/api/app/userSwitchHandler"
AZ_LOG_ON_URL = f"https://{HOST}/cis/ec_wa_wechatf/app/azLogOn"
# 替换为实际的停供信息 API 端点
WATER_STOP_INFO_URL = f"https://{HOST}/cis/ec_wa_wechatf/sysRest/connmnRest"  

def process_acct_name(acct_name):
    """处理 ACCT_NAME"""
    if len(acct_name) == 2:
        return acct_name[1]
    elif len(acct_name) > 2:
        return acct_name[0] + "*" * (len(acct_name) - 2) + acct_name[-1]
    return acct_name


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置通过配置流创建的条目。"""
    phone = entry.data.get("phone")
    password = entry.data.get("password")

    coordinator = ZhangshangAizhongDataCoordinator(hass, HOST, phone, password)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 处理不同 ACCT_NAME 的设备信息
    device_infos = {}
    for acct_name, balances in coordinator.data.items():
        processed_acct_name = process_acct_name(acct_name)
        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{processed_acct_name}")},
            name=f"掌上爱众 - {processed_acct_name}",
            manufacturer="掌上爱众",
        )
        device_infos[acct_name] = device_info
        hass.data[DOMAIN + f"_device_info_{processed_acct_name}"] = device_info

    # 为每个设备创建传感器
    for acct_name, device_info in device_infos.items():
        hass.data[DOMAIN + f"_acct_name_{acct_name}"] = acct_name
        hass.data[DOMAIN + f"_device_info_{acct_name}"] = device_info
        # 修正的方法名及参数：将 "sensor" 放入列表中
        await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置条目。"""
    # 修正的方法名及参数：将 "sensor" 放入列表中
    unload_ok = await hass.config_entries.async_forward_entry_unloads(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class ZhangshangAizhongDataCoordinator(DataUpdateCoordinator):
    """数据协调器，用于更新数据。"""

    def __init__(self, hass, host, phone, password):
        """初始化协调器。"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.host = host
        self.phone = phone
        self.password = password
        self.token = None
        self.cust_id = None
        self.account_no = None

    async def _async_update_data(self):
        """更新数据。"""
        try:
            # 第一步：登录
            async with aiohttp.ClientSession() as session:
                login_data = {
                    "type": 3,
                    "phone": self.phone,
                    "password": self.password
                }
                headers = {
                    "Content-Type": "application/json"
                }
                async with session.post(LOGIN_URL, headers=headers, json=login_data) as response:
                    response.raise_for_status()
                    login_result = await response.json()
                    if login_result.get("code") == "200":
                        self.token = login_result["data"]["token"]
                    else:
                        raise UpdateFailed(f"登录失败: {login_result.get('message')}")

                # 第二步：获取购物车信息
                headers = {
                    "Authorization": self.token,
                    "Content-Type": "application/json"
                }
                async with session.get(GET_CART_URL, headers=headers) as response:
                    response.raise_for_status()
                    await response.json()

                # 第三步：查询客户信息
                query_data = {
                    "phone": self.phone
                }
                async with session.post(QUERY_CUST_INFO_URL, headers=headers, json=query_data) as response:
                    response.raise_for_status()
                    query_result = await response.json()
                    if query_result.get("code") == "200":
                        cust_info_list = query_result["data"]["custInfoList"]
                        if cust_info_list:
                            self.cust_id = cust_info_list[0]["custId"]
                            cust_no = cust_info_list[0]["custNo"]
                        else:
                            raise UpdateFailed("未找到客户信息")
                    else:
                        raise UpdateFailed(f"查询客户信息失败: {query_result.get('message')}")

                # 第四步：用户切换处理
                switch_data = {
                    "custNo": cust_no
                }
                async with session.post(USER_SWITCH_HANDLER_URL, headers=headers, json=switch_data) as response:
                    response.raise_for_status()
                    switch_result = await response.json()
                    if switch_result.get("code") == "200":
                        self.token = switch_result["data"]["token"]
                    else:
                        raise UpdateFailed(f"用户切换处理失败: {switch_result.get('message')}")

                # 第五步：登录获取授权信息
                az_log_on_data = {
                    "custId": self.cust_id,
                    "token": self.token,
                    "pushClientid": "dcb599c4c9caee2c3aee45a17f069126",
                    "phone": self.phone
                }
                async with session.post(AZ_LOG_ON_URL, headers=headers, json=az_log_on_data) as response:
                    response.raise_for_status()
                    az_log_on_result = await response.json()
                    if az_log_on_result.get("CODE") == "0":
                        self.token = az_log_on_result["DATA"]["Authorization"]
                        self.account_no = az_log_on_result["DATA"]["accountNo"]
                    else:
                        raise UpdateFailed(f"登录获取授权信息失败: {az_log_on_result.get('DESC')}")

                # 最后获取之前需要的信息
                data_url = f"https://{self.host}/cis/ec_wa_wechatf/weChatRest/queryInBindConsDetails"
                headers = {
                    "Authorization": self.token,
                    "Content-Type": "application/json"
                }
                data = {
                    "REGION": "",
                    "custId": self.cust_id,
                    "phone": self.phone,
                    "accountNo": self.account_no
                }
                async with session.post(data_url, headers=headers, json=data) as response:
                    response.raise_for_status()
                    result = await response.json()
                    device_data = {}
                    for item in result.get("DATA", []):
                        # 从 CONS_LIST 中获取 ACCT_NAME
                        cons_list = item.get("CONS_LIST", [])
                        if cons_list:
                            acct_name = cons_list[0].get("ACCT_NAME")
                            if acct_name not in device_data:
                                device_data[acct_name] = {
                                    "water_balance": None,
                                    "gas_balance": None,
                                    "water_stop_info": []
                                }
                            if item.get("CONS_TYPE_NAME") == "水":
                                device_data[acct_name]["water_balance"] = item.get("PREPAY_BAL")
                            elif item.get("CONS_TYPE_NAME") == "气":
                                device_data[acct_name]["gas_balance"] = item.get("PREPAY_BAL")

                # 获取水停供信息
                headers = {
                    "Authorization": self.token,
                    "Content-Type": "application/json"
                }
                stop_info_data = {
                    "DATA": {
                        "ORG_NO": "AZ001,AZ002,AZ003,AZ004",
                        "RELE_STYLE": "06",
                        "zsazVersion": 4000020
                    },
                    "SERVICE_ID": "RMT018",
                    "SN": "900720250428131005328125",
                    "SID": "9007",
                    "custId": self.cust_id,
                    "phone": self.phone,
                    "accountNo": self.account_no
                }
                async with session.post(WATER_STOP_INFO_URL, headers=headers, json=stop_info_data) as response:
                    response.raise_for_status()
                    stop_info_result = await response.json()
                    if stop_info_result.get("CODE") == "0":
                        for stop_info in stop_info_result["DATA"]["RTN_RESULT"]:
                            if stop_info.get("ENERGY_TYPE_NAME") == "水务":
                                for acct_name in device_data:
                                    device_data[acct_name]["water_stop_info"].append({
                                        "停供类型": stop_info.get("GAS_STOP_TYPE_NAME"),
                                        "开始时间": stop_info.get("PLAN_BGN_TIME"),
                                        "结束时间": stop_info.get("PLAN_END_TIME"),
                                        "原因": stop_info.get("GAS_STOP_REA_NAME"),
                                        "范围": stop_info.get("GAS_STOP_RANGE")
                                    })
                    else:
                        raise UpdateFailed(f"获取水停供信息失败: {stop_info_result.get('DESC')}")

                return device_data

        except Exception as err:
            raise UpdateFailed(f"更新数据失败: {err}") from err
