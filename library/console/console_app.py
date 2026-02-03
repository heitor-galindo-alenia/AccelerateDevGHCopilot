from .console_state import ConsoleState
from .common_actions import CommonActions
from application_core.interfaces.ipatron_repository import IPatronRepository
from application_core.interfaces.iloan_repository import ILoanRepository
from application_core.interfaces.iloan_service import ILoanService
from application_core.interfaces.ipatron_service import IPatronService

class ConsoleApp:
    def __init__(
        self,
        loan_service: ILoanService,
        patron_service: IPatronService,
        patron_repository: IPatronRepository,
        loan_repository: ILoanRepository,
        json_data=None,
        book_repository=None
    ):
        self._current_state: ConsoleState = ConsoleState.PATRON_SEARCH
        self.matching_patrons = []
        self.selected_patron_details = None
        self.selected_loan_details = None
        self._patron_repository = patron_repository
        self._loan_repository = loan_repository
        self._loan_service = loan_service
        self._patron_service = patron_service
        self._json_data = json_data
        self._book_repository = book_repository
        # Add access to books, book_items, and loans from json_data
        if self._json_data:
            self._books = self._json_data.books
            self._book_items = self._json_data.book_items
            self._loans = self._json_data.loans
        else:
            self._books = []
            self._book_items = []
            self._loans = []

    def write_input_options(self, options):
        print("Input Options:")
        if options & CommonActions.RETURN_LOANED_BOOK:
            print(' - "r" to mark as returned')
        if options & CommonActions.EXTEND_LOANED_BOOK:
            print(' - "e" to extend the book loan')
        if options & CommonActions.RENEW_PATRON_MEMBERSHIP:
            print(' - "m" to extend patron\'s membership')
        if options & CommonActions.SEARCH_BOOKS:
            print(' - "b" to check for book availability')
        if options & CommonActions.SEARCH_PATRONS:
            print(' - "s" for new search')
        if options & CommonActions.QUIT:
            print(' - "q" to quit')
        if options & CommonActions.SELECT:
            print(' - type a number to select a list item.')

    def run(self) -> None:
        while True:
            if self._current_state == ConsoleState.PATRON_SEARCH:
                self._current_state = self.patron_search()
            elif self._current_state == ConsoleState.PATRON_SEARCH_RESULTS:
                self._current_state = self.patron_search_results()
            elif self._current_state == ConsoleState.PATRON_DETAILS:
                self._current_state = self.patron_details()
            elif self._current_state == ConsoleState.LOAN_DETAILS:
                self._current_state = self.loan_details()
            elif self._current_state == ConsoleState.QUIT:
                break

    def patron_search(self) -> ConsoleState:
        search_input = input("Enter a string to search for patrons by name: ").strip()
        if not search_input:
            print("No input provided. Please try again.")
            return ConsoleState.PATRON_SEARCH
        self.matching_patrons = self._patron_repository.search_patrons(search_input)
        if not self.matching_patrons:
            print("No matching patrons found.")
            return ConsoleState.PATRON_SEARCH
        return ConsoleState.PATRON_SEARCH_RESULTS

    def patron_search_results(self) -> ConsoleState:
        print("\nMatching Patrons:")
        idx = 1
        for patron in self.matching_patrons:
            print(f"{idx}) {patron.name}")
            idx += 1
        if self.matching_patrons:
            self.write_input_options(
                CommonActions.SELECT | CommonActions.SEARCH_PATRONS | CommonActions.QUIT
            )
        else:
            self.write_input_options(
                CommonActions.SEARCH_PATRONS | CommonActions.QUIT
            )
        selection = input("Enter your choice: ").strip().lower()
        if selection == 'q':
            return ConsoleState.QUIT
        elif selection == 's':
            return ConsoleState.PATRON_SEARCH
        elif selection.isdigit():
            idx = int(selection)
            if 1 <= idx <= len(self.matching_patrons):
                self.selected_patron_details = self.matching_patrons[idx - 1]
                return ConsoleState.PATRON_DETAILS
            else:
                print("Invalid selection. Please enter a valid number.")
                return ConsoleState.PATRON_SEARCH_RESULTS
        else:
            print("Invalid input. Please enter a number, 's', or 'q'.")
            return ConsoleState.PATRON_SEARCH_RESULTS

    def patron_details(self) -> ConsoleState:
        patron = self.selected_patron_details
        print(f"\nName: {patron.name}")
        print(f"Membership Expiration: {patron.membership_end}")
        loans = self._loan_repository.get_loans_by_patron_id(patron.id)
        print("\nBook Loans History:")

        valid_loans = self._print_loans(loans)

        if valid_loans:
            options = (
                CommonActions.RENEW_PATRON_MEMBERSHIP
                | CommonActions.SEARCH_PATRONS
                | CommonActions.QUIT
                | CommonActions.SELECT
                | CommonActions.SEARCH_BOOKS  # Added SEARCH_BOOKS
            )
            selection = self._get_patron_details_input(options)
            return self._handle_patron_details_selection(selection, patron, valid_loans)
        else:
            print("No valid loans for this patron.")
            options = (
                CommonActions.SEARCH_PATRONS
                | CommonActions.QUIT
                | CommonActions.SEARCH_BOOKS  # Added SEARCH_BOOKS
            )
            selection = self._get_patron_details_input(options)
            return self._handle_no_loans_selection(selection)

    def _print_loans(self, loans):
        valid_loans = []
        idx = 1
        for loan in loans:
            if not getattr(loan, 'book_item', None) or not getattr(loan.book_item, 'book', None):
                print(f"{idx}) [Invalid loan data: missing book information]")
            else:
                returned = "True" if getattr(loan, 'return_date', None) else "False"
                print(f"{idx}) {loan.book_item.book.title} - Due: {loan.due_date} - Returned: {returned}")
                valid_loans.append((idx, loan))
            idx += 1
        return valid_loans

    def _get_patron_details_input(self, options):
        self.write_input_options(options)
        return input("Enter your choice: ").strip().lower()

    def _handle_patron_details_selection(self, selection, patron, valid_loans):
        if selection == 'q':
            return ConsoleState.QUIT
        elif selection == 's':
            return ConsoleState.PATRON_SEARCH
        elif selection == 'm':
            status = self._patron_service.renew_membership(patron.id)
            print(status)
            self.selected_patron_details = self._patron_repository.get_patron(patron.id)
            return ConsoleState.PATRON_DETAILS
        elif selection == 'b':
            return self.search_books()  # Call the new search_books method
        elif selection.isdigit():
            idx = int(selection)
            if 1 <= idx <= len(valid_loans):
                self.selected_loan_details = valid_loans[idx - 1][1]
                return ConsoleState.LOAN_DETAILS
            print("Invalid selection. Please enter a number shown in the list above.")
            return ConsoleState.PATRON_DETAILS
        else:
            print("Invalid input. Please enter a number, 'm', 'b', 's', or 'q'.")
            return ConsoleState.PATRON_DETAILS

    def search_books(self) -> ConsoleState:
        books = self._books
        book_items = self._book_items
        loans = self._loans

        while True:
            book_title = input("Enter a book title to search for: ").strip()
            if not book_title:
                print("No book title provided. Please try again.")
                continue

            # Case-insensitive partial or exact match
            matching_books = [
                book for book in books
                if book_title.lower() in book.title.lower()
            ]

            if not matching_books:
                print("No matching books found.")
                choice = input("Search again? (y/n): ").strip().lower()
                if choice == 'y':
                    continue
                else:
                    return ConsoleState.PATRON_DETAILS

            if len(matching_books) > 1:
                print("\nMultiple books matched:")
                for idx, book in enumerate(matching_books, 1):
                    author_name = getattr(book, 'author', None)
                    if author_name and hasattr(author_name, 'name'):
                        author_name = author_name.name
                    elif hasattr(book, 'author_name'):
                        author_name = book.author_name
                    else:
                        author_name = "Unknown"
                    print(f"{idx}) {book.title} by {author_name}")
                selection = input("Type a number to select a book, or 'r' to refine search, or 'q' to return: ").strip().lower()
                if selection == 'q':
                    return ConsoleState.PATRON_DETAILS
                elif selection == 'r':
                    continue
                elif selection.isdigit():
                    idx = int(selection)
                    if 1 <= idx <= len(matching_books):
                        selected_book = matching_books[idx - 1]
                    else:
                        print("Invalid selection.")
                        continue
                else:
                    print("Invalid input.")
                    continue
            else:
                selected_book = matching_books[0]

            # Find all book items (copies) for this book
            book_item_objs = [
                item for item in book_items
                if getattr(item, 'book_id', None) == selected_book.id
            ]
            book_item_ids = [item.id for item in book_item_objs]
            if not book_item_ids:
                print("No copies found for this book.")
                choice = input("Search again? (y/n): ").strip().lower()
                if choice == 'y':
                    continue
                else:
                    return ConsoleState.PATRON_DETAILS

            # Check loans for these book items
            on_loan = []
            for loan in loans:
                if getattr(loan, 'book_item_id', None) in book_item_ids and getattr(loan, 'return_date', None) is None:
                    on_loan.append(loan)

            if len(on_loan) < len(book_item_ids):
                print(f"'{selected_book.title}' is available for loan.")
                # Find the first available book item
                loaned_item_ids = [loan.book_item_id for loan in on_loan]
                available_items = [item for item in book_item_objs if item.id not in loaned_item_ids]
                # Prompt for checkout
                choice = input("Would you like to check out this book? (y/n): ").strip().lower()
                if choice == 'y':
                    patron = self.selected_patron_details
                    if not patron:
                        print("No patron selected.")
                        return ConsoleState.PATRON_DETAILS
                    # Use the first available item
                    book_item = available_items[0]
                    self._loan_service.checkout_book(patron, book_item)
                    print(f"Book '{selected_book.title}' checked out successfully.")
                    # Refresh data
                    if self._json_data:
                        self._json_data.load_data()
                        self._books = self._json_data.books
                        self._book_items = self._json_data.book_items
                        self._loans = self._json_data.loans
                    return ConsoleState.PATRON_DETAILS
                else:
                    search_again = input("Search again? (y/n): ").strip().lower()
                    if search_again == 'y':
                        continue
                    else:
                        return ConsoleState.PATRON_DETAILS
            else:
                # All copies are on loan, show due dates
                due_dates = [getattr(loan, 'due_date', 'Unknown') for loan in on_loan]
                print(f"'{selected_book.title}' is on loan to another patron. The return due date(s):")
                for date in due_dates:
                    print(f" - {date}")

            choice = input("Search again? (y/n): ").strip().lower()
            if choice == 'y':
                continue
            else:
                return ConsoleState.PATRON_DETAILS

    def _handle_no_loans_selection(self, selection):
        if selection == 'q':
            return ConsoleState.QUIT
        elif selection == 's':
            return ConsoleState.PATRON_SEARCH
        else:
            print("Invalid input.")
            return ConsoleState.PATRON_DETAILS

    def loan_details(self) -> ConsoleState:
        loan = self.selected_loan_details
        print(f"\nBook title: {loan.book_item.book.title}")
        print(f"Book Author: {loan.book_item.book.author.name}")
        print(f"Due date: {loan.due_date}")
        returned = "True" if getattr(loan, 'return_date', None) else "False"
        print(f"Returned: {returned}\n")
        options = CommonActions.SEARCH_PATRONS | CommonActions.QUIT
        if not getattr(loan, 'return_date', None):
            options |= CommonActions.RETURN_LOANED_BOOK | CommonActions.EXTEND_LOANED_BOOK
        self.write_input_options(options)
        selection = input("Enter your choice: ").strip().lower()
        if selection == 'q':
            return ConsoleState.QUIT
        elif selection == 's':
            return ConsoleState.PATRON_SEARCH
        elif selection == 'r' and not getattr(loan, 'return_date', None):
            status = self._loan_service.return_loan(loan.id)
            print("Book was successfully returned.")
            print(status)
            self.selected_loan_details = self._loan_repository.get_loan(loan.id)
            return ConsoleState.LOAN_DETAILS
        elif selection == 'e' and not getattr(loan, 'return_date', None):
            status = self._loan_service.extend_loan(loan.id)
            print(status)
            self.selected_loan_details = self._loan_repository.get_loan(loan.id)
            return ConsoleState.LOAN_DETAILS
        else:
            print("Invalid input.")
            return ConsoleState.LOAN_DETAILS

from application_core.services.loan_service import LoanService
from application_core.services.patron_service import PatronService
from infrastructure.json_data import JsonData
from infrastructure.json_loan_repository import JsonLoanRepository
from infrastructure.json_patron_repository import JsonPatronRepository
from console.console_app import ConsoleApp

def main():
    json_data = JsonData()
    patron_repo = JsonPatronRepository(json_data)
    loan_repo = JsonLoanRepository(json_data)
    loan_service = LoanService(loan_repo)
    patron_service = PatronService(patron_repo)

    app = ConsoleApp(
        loan_service=loan_service,
        patron_service=patron_service
    )
    app.run()
