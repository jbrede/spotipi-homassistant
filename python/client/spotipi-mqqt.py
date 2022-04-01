import paho.mqtt.client as mqtt
import sys,os
import configparser
import dbus
import time
import json

dir = os.path.dirname(__file__)
filename = os.path.join(dir, '../../config/rgb_options.ini')

# Configuration for the matrix
config = configparser.ConfigParser()
config.read(filename)

sysbus = dbus.SystemBus()
systemd1 = sysbus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1')
manager = dbus.Interface(systemd1, 'org.freedesktop.systemd1.Manager')
service = sysbus.get_object('org.freedesktop.systemd1', object_path=manager.GetUnit('spotipi.service'))
interface = dbus.Interface(service, dbus_interface='org.freedesktop.DBus.Properties')

client_name = "spotipi"
matrix_name = "rgb_matrix"
base_topic = "homeassistant/light/rgb-matrix"
config_topic = base_topic + "/config"
set_topic = base_topic + "/set"
state_topic = base_topic + "/state"
config_payload = '''{
  "~": "''' + base_topic + '''",
  "name": "''' + client_name + '''",
  "unique_id": "''' + matrix_name + '''",
  "cmd_t": "~/set",
  "stat_t": "~/state",
  "schema": "json",
  "brightness": true,
  "brightness_scale": 100
}'''


def on_message(client, userdata, message):
    print("message received ", str(message.payload.decode("utf-8")))
    print("message topic=", message.topic)
    print("message qos=", message.qos)
    print("message retain flag=", message.retain)
    fullstate = {"state": "OFF", "brightness": 0}
    unit_state = interface.Get('org.freedesktop.systemd1.Unit', 'ActiveState')
    if unit_state == 'active':
        brightness = str(config['DEFAULT']['brightness'])
        fullstate = {"state": "ON", "brightness": int(brightness)}
    # print('active_state: ' + active_state)
    client.publish(state_topic, json.dumps(fullstate), retain=True)


def on_set_message(client, userdata, message):
    print("in set topic")
    payload = json.loads(message.payload.decode("utf-8"))
    if "brightness" in payload:
        brightness = str(payload["brightness"])
        print("Set brightness to " + brightness)
        config.set('DEFAULT', 'brightness', brightness)
        with open(filename, 'w') as configfile:
            config.write(configfile)
            #os.close(configfile)
            job = manager.RestartUnit('spotipi.service', 'fail')
            fullstate = {"state": "ON", "brightness": int(brightness)}
            client.publish(state_topic, json.dumps(fullstate), retain=True)
    elif "state" in payload:
        state = payload["state"]
        if state == "ON":
            print("Turning on")
            brightness = str(config['DEFAULT']['brightness'])
            job = manager.StartUnit('spotipi.service', 'replace')
            fullstate = {"state": "ON", "brightness": int(brightness)}
            client.publish(state_topic, json.dumps(fullstate), retain=True)
        elif state == "OFF":
            print("Turning off")
            brightness = str(0)
            job = manager.StopUnit('spotipi.service', 'replace')
            fullstate = {"state": "OFF", "brightness": int(brightness)}
            client.publish(state_topic, json.dumps(fullstate), retain=True)


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected MQTT disconnection. Will auto-reconnect")


client = mqtt.Client(client_name)
client.on_message=on_message
client.message_callback_add(set_topic, on_set_message)
client.on_disconnect = on_disconnect
client.connect("nanopi")
client.subscribe(set_topic)
client.publish(config_topic, config_payload, retain=True)
brightness = str(config['DEFAULT']['brightness'])
fullstate = {"state": "ON", "brightness": brightness}
client.publish(state_topic, json.dumps(fullstate), retain=True)

try:
    client.loop_forever()
except KeyboardInterrupt:
    client.disconnect()
