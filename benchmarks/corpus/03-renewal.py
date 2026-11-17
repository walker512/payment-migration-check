# Synthetic legacy handler; provider context is known to the fixture author.
def on_event(event):
    return event['name'] == 'subscription_payment_failed'
