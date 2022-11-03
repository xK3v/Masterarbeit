import logging

import azure.functions as func

def main(msg: func.QueueMessage, msgout: func.Out[func.QueueMessage]) -> None:
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))
    uuid = msg.get_body().decode('utf-8')

    msgout.set(uuid)

