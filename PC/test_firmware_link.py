"""Compile production MCU formatters, then feed their bytes through the real PC parser."""
import unittest, tempfile, subprocess, shutil
from pathlib import Path
from protocol import Parser, encode
from calibration import Calibration, parse_calibration

class FirmwareLinkTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('gcc'),'Host GCC required for MCU formatter test')
    def test_production_mcu_bytes_to_pc(self):
        parent=Path(__file__).resolve().parent.parent
        root=parent/'MCU_validation'
        if not root.exists():root=parent/'MCU_Calibration_V1_4'
        if not root.exists():self.skipTest('MCU validation sources not bundled')
        source=(root/'MCU/main.c').read_text()
        prefix=(root/'tests/test_commands.c').read_text().split('#include "command_under_test.inc"')[0]
        prefix=prefix.replace('void app_log(const char *format,...){(void)format;}','')
        log=source[source.index('static void app_log('):source.index('static char command_line[')]
        commands=source[source.index('/* Shared entry'):source.index('static int command_service(')]
        a=source.index('        if(cal_live_enabled && cal_live_ready)');b=source.index('        if(cal_face>=0 &&',a)
        preview=source[a:b]
        c=prefix+'\n#include <stdarg.h>\n#define TX_BYTES 512\nint uart_enqueue(const void*p,int n){return fwrite(p,1,n,stdout)==(size_t)n?0:-1;}\n'+log+commands+'''
int main(void){
cal_begin();cal_mask=63;
float values[6][3]={{627.322f,263.460f,-246.552f},{-1357.860f,188.470f,-216.526f},{-343.698f,1224.058f,-162.343f},{-314.603f,-772.126f,-194.870f},{-292.067f,219.354f,794.765f},{-391.649f,197.997f,-1194.315f}};
memcpy(cal_faces,values,sizeof values);
cal_command("CAL INFO");cal_command("CAL STATUS");cal_command("CAL SOLVE");
cal_live_enabled=cal_live_ready=1;
cal_live_value[0]=-41.262f;cal_live_value[1]=-438.080f;cal_live_value[2]=437.726f;
'''+preview+'''return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);(tmp/'emit.c').write_text(c)
            subprocess.run(['gcc','-std=c11','-I'+str(root/'MCU'),str(tmp/'emit.c'),'-lm','-o',str(tmp/'emit')],check=True)
            wire=subprocess.check_output([str(tmp/'emit')])
        # Interleave real binary frames with complete MCU text lines, then fragment byte by byte.
        frame=encode([[1,2,3]]*32)
        mixed=b''.join(line+b'\n'+frame for line in wire.splitlines())+b'END\n'
        parser=Parser();m=Calibration(lambda _:None);m.connection(True);m.pending='solve'
        frames=0
        for byte in mixed:
            packets,lines=parser.feed(bytes([byte]));frames+=len(packets)
            for line in lines:
                event=parse_calibration(line)
                if event:m.event(event)
        self.assertEqual(parser.errors,0);self.assertGreater(frames,8)
        self.assertTrue(m.link_ready);self.assertEqual(len(m.rows),6)
        self.assertTrue(m.solved);self.assertIsNotNone(m.candidate)
        self.assertEqual(m.check['rc'],0);self.assertEqual(m.rows[4]['raw'][2],794765)
        self.assertTrue(m.actual_fresh());self.assertEqual(m.actual['mean'][0],-41262)
        self.assertEqual(m.live['mean'][2],437726)

if __name__=='__main__':unittest.main()
