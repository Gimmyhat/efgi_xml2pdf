from pyhanko.sign import signers, PdfSignatureMetadata
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign.signers.pdf_signer import PdfSigner


async def sign_pdf_test(input_pdf_path, output_pdf_path, pfx_path, password=None):
    try:
        # Загружаем PFX сертификат и закрытый ключ
        signer = signers.SimpleSigner.load_pkcs12(
            pfx_file=pfx_path,
            passphrase=password.encode() if password else None
        )

        # Открываем исходный PDF файл
        with open(input_pdf_path, 'rb') as inf:
            w = IncrementalPdfFileWriter(inf)

            # Метаданные подписи
            signature_meta = PdfSignatureMetadata(field_name="Signature1")

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