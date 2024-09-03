import asyncio
from pyhanko.sign import signers, PdfSignatureMetadata
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign.signers.pdf_signer import PdfSigner


async def sign_pdf(input_pdf_path, output_pdf_path, pfx_path, cert_name, password, test=False):
    if not test:
        try:
            # Формируем команду для csptest
            command = [
                "csptest", "-sfsign", "-sign",
                "-in", input_pdf_path,
                "-out", output_pdf_path,
                "-my", cert_name,
                "-add"
            ]

            # Запускаем процесс с передачей пароля через stdin
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Отправляем пароль и завершаем ввод
            password_bytes = (password + '\n').encode('utf-8')
            stdout, stderr = await process.communicate(input=password_bytes)

            # Проверка кодировки вывода
            def decode_output(output):
                encodings = ['utf-8', 'cp1251', 'cp866']
                for encoding in encodings:
                    try:
                        return output.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return output.decode('utf-8', errors='ignore')  # Fallback с игнорированием ошибок

            stdout_decoded = decode_output(stdout)
            stderr_decoded = decode_output(stderr)

            if process.returncode == 0:
                print(f"PDF успешно подписан и сохранен как {output_pdf_path}")
                print(f"Вывод csptest: {stdout_decoded}")
            else:
                print(f"Ошибка при подписании PDF. Код возврата: {process.returncode}")
                print(f"Ошибка: {stderr_decoded}")
                raise Exception(f"Не удалось подписать PDF. Ошибка: {stderr_decoded}")

        except Exception as e:
            print(f"Ошибка при подписании PDF: {str(e)}")
            raise
    else:
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
