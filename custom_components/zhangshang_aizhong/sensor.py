import logging
from homeassistant.components.sensor import SensorEntity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """设置传感器平台。"""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    for acct_name in coordinator.data.keys():
        device_info = hass.data[DOMAIN + f"_device_info_{acct_name}"]
        entities = [
            ZhangshangAizhongSensor(coordinator, acct_name, "water_balance", "水余额", device_info, entry.entry_id),
            ZhangshangAizhongSensor(coordinator, acct_name, "gas_balance", "气余额", device_info, entry.entry_id),
            ZhangshangAizhongSensor(coordinator, acct_name, "water_stop_info", "水停供信息", device_info, entry.entry_id)
        ]
        async_add_entities(entities)


class ZhangshangAizhongSensor(SensorEntity):
    """掌上爱众传感器类。"""

    def __init__(self, coordinator, acct_name, key, name, device_info, entry_id):
        """初始化传感器。"""
        self.coordinator = coordinator
        self._acct_name = acct_name
        self._key = key
        self._name = name
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_{acct_name}_{key}"  # 为实体添加唯一标识符

    @property
    def name(self):
        """返回传感器名称。"""
        return f"掌上爱众 {self._acct_name} {self._name}"

    @property
    def state(self):
        """返回传感器状态。"""
        if self._key == "water_stop_info":
            stop_info = self.coordinator.data.get(self._acct_name, {}).get(self._key, [])
            return len(stop_info)
        return self.coordinator.data.get(self._acct_name, {}).get(self._key)

    @property
    def unit_of_measurement(self):
        """返回测量单位。"""
        if self._key in ["water_balance", "gas_balance"]:
            return "元"
        elif self._key == "water_stop_info":
            return "条"
        return None

    @property
    def available(self):
        """返回传感器是否可用。"""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        """返回额外的状态属性。"""
        if self._key == "water_stop_info":
            stop_info = self.coordinator.data.get(self._acct_name, {}).get(self._key, [])
            return {
                f"stop_info_{i}": info for i, info in enumerate(stop_info)
            }
        return {}

    async def async_update(self):
        """更新传感器数据。"""
        await self.coordinator.async_request_refresh()
