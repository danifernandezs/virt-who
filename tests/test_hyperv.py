"""
Test of Hyper-V virtualization backend.

Copyright (C) 2016 Radek Novacek <rnovacek@redhat.com>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from mock import patch, MagicMock, ANY
from multiprocessing import Queue, Event
from xml.etree import ElementTree
import requests

from base import TestBase
from config import Config
from virt.hyperv import HyperV
from virt import VirtError, Guest, Hypervisor


class HyperVMock(object):
    @classmethod
    def post(cls, url, data, **kwargs):
        if 'uuid:00000000-0000-0000-0000-000000000000' in data:
            print(">>>> 0")
            return HyperVMock.pull(None, {})
        if 'Msvm_VirtualSystemSettingData' in data:
            print(">>>> 1")
            return HyperVMock.enumerate(5)
        elif 'uuid:00000000-0000-0000-0000-000000000005' in data:
            print(">>>> 2")
            return HyperVMock.pull(0, {
                'BIOSGUID': '{78563412-AB90-EFCD-1234-567890ABCDEF}',
                'ElementName': '',
            })
        elif 'GetSummaryInformation_INPUT' in data:
            print(">>>> 3")
            return HyperVMock.summary_information()
        elif 'select * from CIM_Datafile' in data:
            print(">>>> 4")
            return HyperVMock.enumerate(1)
        elif 'uuid:00000000-0000-0000-0000-000000000001' in data:
            print(">>>> 5")
            return HyperVMock.pull(2, {
                'p:Path': '\\windows\\system32\\',
                'p:Version': '0.1.2345.67890',
            })
        elif 'uuid:00000000-0000-0000-0000-000000000002' in data:
            print(">>>> 6")
            return HyperVMock.pull(None, {})
        elif 'NumberOfProcessors from Win32_ComputerSystem' in data:
            print(">>>> 7")
            return HyperVMock.enumerate(3)
        elif 'uuid:00000000-0000-0000-0000-000000000003' in data:
            print(">>>> 8")
            return HyperVMock.pull(0, {
                'NumberOfProcessors': '1',
                'DNSHostName': 'hostname.domainname',
            })
        elif 'UUID from Win32_ComputerSystemProduct' in data:
            print(">>>> 9")
            return HyperVMock.enumerate(4)
        elif 'uuid:00000000-0000-0000-0000-000000000004' in data:
            print(">>>> 10")
            return HyperVMock.pull(0, {
                'UUID': '{78563412-AB90-EFCD-1234-567890ABCDEF}',
            })
        else:
            print(">>>> 11")
            raise AssertionError("Not implemented")

        xml = ElementTree.fromstring(data)
        header = xml.find('{http://www.w3.org/2003/05/soap-envelope}Header')
        action = header.find('{http://schemas.xmlsoap.org/ws/2004/08/addressing}Action').text
        if action == 'http://schemas.xmlsoap.org/ws/2004/09/enumeration/Enumerate':
            pass

        print "POST", url, data
        '''
        [
            HyperVMock.enumerate({}),
            HyperVMock.summary_information(),
            HyperVMock.enumerate({}),
            HyperVMock.pull(''),
            HyperVMock.pull(''),
            HyperVMock.pull(''),
            HyperVMock.enumerate({}),
            HyperVMock.pull(''),
            HyperVMock.enumerate({}),
            HyperVMock.pull(''),
        ]
        '''

    @classmethod
    def envelope(cls, body):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
            <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
                xmlns:w="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
                xmlns:p="http://schemas.microsoft.com/wbem/wsman/1/wsman.xsd"
                xmlns:wsen="http://schemas.xmlsoap.org/ws/2004/09/enumeration"
                xmlns:vsms="http://schemas.microsoft.com/wbem/wsman/1/wmi/root/virtualization/Msvm_VirtualSystemManagementService">
                <s:Body>
                    {}
                </s:Body>
            </s:Envelope>'''.format(body)
        return MagicMock(text=xml, status_code=200)

    @classmethod
    def enumerate(cls, id):
        return HyperVMock.envelope('''
            <wsen:EnumerateResponse>
                <wsen:EnumerationContext>uuid:00000000-0000-0000-0000-{}</wsen:EnumerationContext>
            </wsen:EnumerateResponse>'''.format(str(id).rjust(12, '0')))

    @classmethod
    def pull(cls, msg_id, data):
        print "PULL", msg_id, data
        if msg_id is not None:
            s = []
            for key, value in data.items():
                s.append("<{0}>{1}</{0}>".format(key, value))
            return HyperVMock.envelope('''
                <wsen:PullResponse>
                    <wsen:EnumerationContext>uuid:00000000-0000-0000-0000-{}</wsen:EnumerationContext>
                    <wsen:Items>
                        <p:CIM_DataFile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:p="http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/CIM_DataFile" xmlns:cim="http://schemas.dmtf.org/wbem/wscim/1/common" xsi:type="p:CIM_DataFile_Type">
                            {}
                        </p:CIM_DataFile>
                    </wsen:Items>
                </wsen:PullResponse>
            '''.format(str(msg_id).rjust(12, '0'), "\n".join(s)))
        else:
            print "NONE"
            return HyperVMock.envelope('''
                <wsen:PullResponse>
                    <wsen:Items></wsen:Items>
                    <wsen:EndOfSequence/>
                </wsen:PullResponse>''')

    @classmethod
    def method(cls, body):
        return HyperVMock.envelope(body)

    @classmethod
    def summary_information(cls):
        return HyperVMock.method('''
            <vsms:GetSummaryInformation_OUTPUT>
                <vsms:ReturnValue>0</vsms:ReturnValue>
            </vsms:GetSummaryInformation_OUTPUT>''')

    @classmethod
    def datafile(cls):
        pass


class TestHyperV(TestBase):
    def setUp(self):
        config = Config('test', 'hyperv', server='localhost', username='username',
                        password='password', owner='owner', env='env')
        self.hyperv = HyperV(self.logger, config)

    def run_once(self, queue=None):
        ''' Run Hyper-V in oneshot mode '''
        self.hyperv._oneshot = True
        self.hyperv._queue = queue or Queue()
        self.hyperv._terminate_event = Event()
        self.hyperv._interval = 0
        self.hyperv._run()

    @patch('requests.Session')
    def test_connect(self, session):
        session.return_value.post.side_effect = HyperVMock.post
        self.run_once()

        session.assert_called()
        session.return_value.post.assert_called_with('http://localhost:5985/wsman', ANY, headers=ANY)

    @patch('requests.Session')
    def test_connection_refused(self, session):
        session.return_value.post.side_effect = requests.ConnectionError
        self.assertRaises(VirtError, self.run_once)

    @patch('requests.Session')
    def test_invalid_login(self, session):
        session.return_value.post.return_value.status_code = 401
        self.assertRaises(VirtError, self.run_once)

    @patch('requests.Session')
    def test_404(self, session):
        session.return_value.post.return_value.text = ''
        session.return_value.post.return_value.status_code = 404
        self.assertRaises(VirtError, self.run_once)

    @patch('requests.Session')
    def test_500(self, session):
        session.return_value.post.return_value.text = ''
        session.return_value.post.return_value.status_code = 500
        self.assertRaises(VirtError, self.run_once)

    @patch('requests.Session')
    def test_wrong_namespace(self, session):
        session.return_value.post.return_value.text = '''
<s:Envelope xml:lang="en-US" xmlns:s="http://www.w3.org/2003/05/soap-envelope">
    <s:Body>
        <s:Fault>
            <s:Detail>
                <p:MSFT_WmiError xmlns:p="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/MSFT_WmiError">
                    <p:error_Code>2150858778</p:error_Code>
                </p:MSFT_WmiError>
            </s:Detail>
        </s:Fault>
    </s:Body>
</s:Envelope>'''
        session.return_value.post.return_value.status_code = 500
        self.assertRaises(VirtError, self.run_once)

    @patch('requests.Session')
    def test_fault(self, session):
        session.return_value.post.return_value.text = '''
<s:Envelope xml:lang="en-US" xmlns:s="http://www.w3.org/2003/05/soap-envelope"></s:Envelope>'''
        session.return_value.post.return_value.status_code = 500
        self.assertRaises(VirtError, self.run_once)

    @patch('requests.Session')
    def test_getHostGuestMapping(self, session):
        expected_hostname = 'hostname.domainname'
        expected_hypervisorId = '12345678-90AB-CDEF-1234-567890ABCDEF'
        expected_guestId = '12345678-90AB-CDEF-1234-567890ABCDEF'
        expected_guest_state = Guest.STATE_UNKNOWN

        session.return_value.post.side_effect = HyperVMock.post

        expected_result = Hypervisor(
            hypervisorId=expected_hypervisorId,
            name=expected_hostname,
            guestIds=[
                Guest(
                    expected_guestId,
                    self.hyperv,
                    expected_guest_state,
                    hypervisorType='hyperv',
                    hypervisorVersion='0.1.2345.67890',
                )
            ],
            facts={
                'cpu.cpu_socket(s)': '1',
            }
        )
        result = self.hyperv.getHostGuestMapping()['hypervisors'][0]
        assert expected_result.toDict() == result.toDict()
