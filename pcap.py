from selenium import webdriver

browser = webdriver.Firefox()

# load home page
browser.get('https://www.personalcapital.com/')

# load sign-in page
browser.get('https://home.personalcapital.com/page/login/goHome')

# fill out email form
form = browser.find_elements_by_xpath("//form[@id='form-email']")[0]
input_elt = form.find_elements_by_xpath(".//input[@name='username']")[0]
input_elt.send_keys('bdelliott@gmail.com')
submit = form.find_elements_by_xpath(".//button[@type='submit']")[0]
submit.click()

import pdb; pdb.set_trace()
