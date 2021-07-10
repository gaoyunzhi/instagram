import os
import time

def test():
	count = 0
	target = list(range(40, 60))
	with open('candidates.txt') as f:
		for line in f:
			count += 1
			if count not in target:
				continue
			line = line.strip()
			if not line:
				continue
			os.system('open ' + line.strip() + ' -g')

if __name__ == '__main__':
	test()
