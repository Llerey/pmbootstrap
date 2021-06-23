import QtQuick 2.5
import QtQuick.Controls 2.12

// cutom package, registered in python code
import Pmb 1.0 as Pmb

ApplicationWindow {
    id: appWindow
    visible: true
    width: 400
    height: contentCol.height + 20
    title: qsTr("pmbootstrap sudo askpass")

    Pmb.Askpass {
        id: askpass
    }

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: 10

        Column {
            id: contentCol
            
            anchors.top: parent.top
            anchors.left: parent.left
            
            width: parent.width
            spacing: 5

            Row {
                anchors.horizontalCenter: parent.horizontalCenter

                Label {
                    height: input.height
                    verticalAlignment: Text.AlignVCenter
                    text: askpass.prompt !== "" ? askpass.prompt : qsTr("Enter password: ")
                }

                Item { height: 10; width: 10; } // spacer

                TextField {
                    id: input
                    echoMode: TextInput.Password
                    placeholderText: "*****"
                    onAccepted: returnOk()
                }
            }

            DialogButtonBox {
                anchors.horizontalCenter: parent.horizontalCenter
                standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel

                onAccepted: returnOk()
                onRejected: {
                    askpass.set_pass('')
                    appWindow.close()
                }
            }
        } // Column
    }

    function returnOk() {
        askpass.set_pass(input.text)
        appWindow.close()
    }
}
