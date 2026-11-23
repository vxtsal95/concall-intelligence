import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.ingest import ExchangeClient
from app.extract import chunk_text

class CoreTests(unittest.TestCase):
    def test_transcript_filter(self):
        self.assertTrue(ExchangeClient.is_transcript({'title':'Q2 FY27 Earnings Conference Call Transcript','source_url':'https://example.com/a.pdf'}))
        self.assertFalse(ExchangeClient.is_transcript({'title':'Audio recording of earnings call','source_url':'https://example.com/a.pdf'}))
    def test_chunking(self):
        text='\n\n'.join('Paragraph '+str(i)+' '+('x'*150) for i in range(20))
        chunks=chunk_text(text,max_chars=500,overlap=50)
        self.assertGreater(len(chunks),1)
        self.assertTrue(all(chunks))
    def test_dedupe(self):
        a={'source_url':'https://example.com/file.pdf?x=1','company':'A'}
        b={'source_url':'https://example.com/file.pdf?x=2','company':'A'}
        self.assertEqual(ExchangeClient.dedupe_key(a),ExchangeClient.dedupe_key(b))

if __name__=='__main__': unittest.main()
