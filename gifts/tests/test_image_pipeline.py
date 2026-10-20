from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import gzip
import io
import socket
import threading
from unittest import TestCase
from unittest.mock import patch

from PIL import Image
from gifts.external import obtain_product_image, image_candidates, fetch, Budget, FetchError
from .test_external import raster


class ImageMetadataTests(TestCase):
    def test_iso8859_twitter_secure_og_nested_schema_and_primary_product_image(self):
        pages = [
            ('<meta charset="iso-8859-1"><title>Açúcar</title><meta property="og:image:secure_url" content="/photo.png">'.encode('iso-8859-1'),'Açúcar'),
            (b'<meta name="twitter:title" content="Panela"><meta name="twitter:image" content="/photo.png">','Panela'),
            (b'<script type="application/ld+json">{"mainEntity":{"@type":"https://schema.org/Product","name":"Panela","image":{"contentUrl":"/photo.png"}}}</script>','Panela'),
            (b'<img id="landingImage" alt="Faqueiro Tramontina" data-old-hires="/photo.png" src="/small.png">','Faqueiro'),
        ]
        for html,name in pages:
            self.assertEqual(image_candidates(html,name),['/photo.png'])
        self.assertEqual(image_candidates(b'<img id="landingImage" alt="Logo da loja" src="/logo.png">','Faqueiro'),[])


class HTTPImagePipelineTests(TestCase):
    def test_real_http_close_gzip_relative_metadata_download_and_recode(self):
        photo=raster()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                if self.path=='/page':
                    body=gzip.compress(b'<title>Panela</title><meta property="og:image" content="/photo">')
                    mime='text/html';encoding='gzip'
                else:body=photo;mime='image/png';encoding='identity'
                self.send_response(200);self.send_header('Content-Type',mime)
                self.send_header('Content-Encoding',encoding);self.send_header('Content-Length',str(len(body)))
                self.send_header('Connection','close');self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        original_connect=socket.create_connection
        class PublicPeerSocket:
            def __init__(self,wrapped):self.wrapped=wrapped
            def getpeername(self):return ('8.8.8.8',80)
            def __getattr__(self,name):return getattr(self.wrapped,name)
        def connect(address,timeout):return PublicPeerSocket(original_connect(server.server_address,timeout))
        try:
            with patch('gifts.external.resolve_public',return_value='8.8.8.8'),patch('gifts.external.socket.create_connection',side_effect=connect):
                html,mime,_=fetch('http://public.example/page',Budget(),1024*1024)
                self.assertIn(b'Panela',html);self.assertEqual(mime,'text/html')
                result=obtain_product_image(['http://public.example/page'],'Panela')
            self.assertIsNotNone(result,'O pipeline deve baixar e recodificar a imagem, não apenas escolher placeholder.')
            with Image.open(io.BytesIO(result)) as image:self.assertEqual(image.format,'WEBP')
        finally:server.shutdown();server.server_close();thread.join(timeout=2)

    def test_gzip_decompression_is_bounded(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.status=200
        response.isclosed.return_value=False
        headers={'Content-Encoding':'gzip','Content-Type':'text/html'}
        response.getheader.side_effect=lambda name,default=None:headers.get(name,default)
        response.read1.side_effect=[gzip.compress(b'x'*20000),b'']
        with patch('gifts.external.resolve_public',return_value='8.8.8.8'),patch('gifts.external.PinnedConnection') as connection:
            connection.return_value.getresponse.return_value=response
            with self.assertRaises(FetchError):fetch('http://public.example/page',Budget(),1000)
