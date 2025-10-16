from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        page = browser.new_page()
        try:
            print("Navegando a http://example.com...")
            page.goto('http://example.com')
            print(f"Título de la página: {page.title()}")
            print("Playwright funciona correctamente.")
        except Exception as e:
            print(f"Error en Playwright: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()