import QtQuick 2.5
import QtQuick.Controls 2.12

// cutom package, registered in python code
import Pmb 1.0 as Pmb

ApplicationWindow {
    id: appWindow
    visible: true
    width: 800
    height: 534
    title: qsTr("pmbootstrap GUI")

    header: Item {
        height: bgImg.height

        Rectangle {
            // white background
            color: "white"
            height: bgImg.height
            width: parent.width
        }

        Image {
            id: bgImg
            cache: true
            source: "../img/header.jpg"
            height: 111
            width: 1076
        }
    }

    Pmb.Devices {
        id: pmbDevices
    }

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: 10

        Column {
            anchors.top: parent.top
            anchors.left: parent.left
            width: parent.width

            Row {
                height: cbChannels.height
                Label {
                    height: cbChannels.height
                    verticalAlignment: Text.AlignVCenter
                    text: qsTr("Select postmarketOS release: ")
                }
                ComboBox {
                    id: cbChannels
                    model: pmbDevices.channels
                    currentIndex: pmbDevices.current_channel
                    onActivated: {
                        pmbDevices.set_channel(index)
                    }
                }
            }

            Row {
                height: cbVendors.height
                Label {
                    height: cbVendors.height
                    verticalAlignment: Text.AlignVCenter
                    text: qsTr("Select manufacturer: ")
                }
                ComboBox {
                    id: cbVendors
                    model: pmbDevices.vendors
                    onActivated: {
                        pmbDevices.select_vendor(index)
                    }
                }
            }

            Row {
                height: cbDevices.height
                Label {
                    height: cbDevices.height
                    verticalAlignment: Text.AlignVCenter
                    text: qsTr("Select device: ")
                }
                ComboBox {
                    id: cbDevices
                    model: pmbDevices.vendor_devices
                    onActivated: {
                        pmbDevices.select_device(index)
                    }
                }
            }

            Row {
                height: cbUis.height
                Label {
                    height: cbUis.height
                    verticalAlignment: Text.AlignVCenter
                    text: qsTr("Select UI: ")
                }
                ComboBox {
                    id: cbUis
                    model: pmbDevices.uis_list
                }
            }
        }
    }

    //Component.onCompleted: {
        //console.log("vendors: ", pmbdevices.vendors)
    //}
}
