class InvalidEnvironment(RuntimeError):

    def __init__(self):
        super(InvalidEnvironment, self).__init__()
    
    def __init__(self, msg):
        self.message = msg
        super(InvalidEnvironment, self).__init__(msg)

        
