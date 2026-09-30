"""Explicit local connection check; never invoked on import."""
import getpass
import sys
import warnings

if __package__:
    from .supabase_auth import configuration, sign_in
    from .supabase_reader import MAX_CARDS, read_approved
else:
    from supabase_auth import configuration, sign_in
    from supabase_reader import MAX_CARDS, read_approved


def main(argv=None):
    """No CLI credentials/options; only local prompts and a bounded count."""
    try:
        if (sys.argv[1:] if argv is None else argv):
            raise ValueError('No arguments accepted')
        configuration()
        email = input('Auth email: ')
        # Fail before getpass can fall back to echoing a password on stdin.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('Auth password: ')
        try:
            token = sign_in(email, password)
        finally:
            del email, password
        try:
            cards = read_approved(token, limit=MAX_CARDS)
            if cards is None:
                raise ValueError('No result')
            count = len(cards)
            del cards
        finally:
            del token
        print(f'Connection successful; approved cards returned: {count}')
        return 0
    except (Exception, KeyboardInterrupt):
        # Never print exceptions, response bodies, credentials or traceback context.
        print('Connection check unavailable or rejected.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
