# \efgi-xml2pdf\app\pdf_signer.py
import asyncio
from pyhanko.sign import signers, PdfSignatureMetadata
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign.fields import SigFieldSpec, append_signature_field
from pyhanko.sign.signers.pdf_signer import PdfSigner


async def sign_pdf(input_pdf_path, output_pdf_path, cert_path, private_key_path, password=None):
    try:
        # Загружаем сертификат и закрытый ключ
        signer = signers.SimpleSigner.load(
            cert_file=cert_path,
            key_file=private_key_path,
            key_passphrase=password.encode() if password else None
        )

        # Открываем исходный PDF файл
        with open(input_pdf_path, 'rb') as inf:
            w = IncrementalPdfFileWriter(inf)

            # Метаданные подписи
            signature_meta = PdfSignatureMetadata(field_name="Signature1")

            # Размеры и позиция поля подписи (должны быть соответствующие координаты, где будет размещена подпись)
            sig_field_spec = SigFieldSpec(sig_field_name="Signature1", box=(0, 0, 0, 0))  # Пустая область для скрытия

            # Добавляем поле подписи в PDF
            append_signature_field(w, sig_field_spec)

            # Подписываем и сохраняем PDF
            pdf_signer = PdfSigner(
                signature_meta=signature_meta,
                signer=signer
            )

            with open(output_pdf_path, 'wb') as outf:
                await pdf_signer.async_sign_pdf(
                    w,
                    output=outf,
                    existing_fields_only=False
                )

        print(f"Подписанный PDF сохранен как {output_pdf_path}")
    except Exception as e:
        print(f"Ошибка при подписании PDF: {e}")
        raise
