
def get_punishment(message:str) -> tuple:
	split_message = message.split(" ")
	pun_type = split_message[0]
	playfab_id = split_message[1]
	reason = split_message[2]
	return (pun_type, playfab_id, reason)